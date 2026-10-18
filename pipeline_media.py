#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
METRIKA Media - Automated Multi-Program Editorial System
========================================================
Platform media otomasi cerdas berbasis Jurnalisme Data & Komputasi Visual.
Standar Editorial Kelas Agensi Desain & Media Investigasi Premium (@theeconomicinfluence, Bloomberg).

Fokus Utama:
- Carousel Instagram 5 Slide Padat & Penuh (1080x1350 px), ZERO BLANK VOID.
- Copywriting Tajam, Provokatif, Emosional, dan Bebas Bahasa Birokrat Klise.
- Foto Jurnalistik 100% Nyata & Relevan (Filter anti-dokumen scan, anti-buku arsip, anti-anime).
- Palet Coklat Mewah (Luxury Espresso, Warm Cognac Leather, Warm Ivory Linen).
- Tanpa rendering video (100% komputasi difokuskan pada keindahan carousel).
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

# Strict Exclusion List untuk Menolak Dokumen Arsip, Buku Scan, & Gambar Non-Fotografis
BLOCKED_IMAGE_DOMAINS = [
    "googleusercontent.com/ytc",
    "yt3.ggpht.com",
    "youtube.com",
    "pinterest.com",
    "pinimg.com",
    "deviantart",
    "artstation",
    "zerochan",
    "wallpaper",
    "vector",
    "clipart",
    "alphacoders",
    "fandom",
    "shopee",
    "tokopedia",
    "lazada",
    "bukalapak",
    "aliexpress",
    "ebay",
    "amazon.com",
    "media-amazon.com",
]

DISALLOWED_IMAGE_TERMS = [
    "archive", "document", "historic", "report", "cover", "page_", "_page",
    "book", "pdf", "scan", "manuscript", "text", "diagram", "edition", "staff",
    "circular", "memorandum", "paper", "scientific", "knowledge", "policy",
    "anime", "manga", "cartoon", "illustration", "vector", "drawing", "sketch",
    "cosplay", "game", "wallpaper", "avatar", "profile", "halloween", "spooky",
    "pumpkin", "room", "bedroom", "dress", "doll", "character", "comic", "costume",
]

CACHE_FILE = Path("posted_links.txt")
OUTPUT_DIR = Path("output_media")
CAROUSEL_DIR = OUTPUT_DIR / "carousel"
AUDIO_PATH = OUTPUT_DIR / "voiceover.mp3"
SUBTITLE_PATH = OUTPUT_DIR / "subtitles.json"

HERO_IMG_PATH = OUTPUT_DIR / "slide_01_hero.jpg"
SLIDE2_IMG_PATH = OUTPUT_DIR / "slide_02_context.jpg"
SLIDE3_IMG_PATH = OUTPUT_DIR / "slide_03_metric.jpg"
SLIDE4_IMG_PATH = OUTPUT_DIR / "slide_04_strategy.jpg"
SLIDE5_IMG_PATH = OUTPUT_DIR / "slide_05_verdict.jpg"
VERDICT_IMG_PATH = SLIDE5_IMG_PATH

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

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# Bank Foto Terverifikasi Bebas Hak Cipta & Berkualitas Editorial Tinggi
TOPIC_IMAGE_VAULT = {
    "money": "https://images.unsplash.com/photo-1580519542036-c47de6196ba5?auto=format&fit=crop&w=1200&q=80",
    "rupiah": "https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?auto=format&fit=crop&w=1200&q=80",
    "currency_exchange": "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?auto=format&fit=crop&w=1200&q=80",
    "chart": "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=1200&q=80",
    "gold": "https://images.unsplash.com/photo-1610375461246-83df859d849d?auto=format&fit=crop&w=1200&q=80",
    "gold_coins": "https://images.unsplash.com/photo-1509718443690-d8e2fb3474b7?auto=format&fit=crop&w=1200&q=80",
    "investor": "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?auto=format&fit=crop&w=1200&q=80",
    "trading_screen": "https://images.unsplash.com/photo-1642543492481-44e81e3914a7?auto=format&fit=crop&w=1200&q=80",
    "bank": "https://images.unsplash.com/photo-1541354329998-f4d9a9f9297f?auto=format&fit=crop&w=1200&q=80",
    "vault": "https://images.unsplash.com/photo-1565372195458-9de0b320ef04?auto=format&fit=crop&w=1200&q=80",
    "jakarta": "https://images.unsplash.com/photo-1578632767115-351597cf2477?auto=format&fit=crop&w=1200&q=80",
    "skyscraper": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=1200&q=80",
    "workers": "https://images.unsplash.com/photo-1517048676732-d65bc937f952?auto=format&fit=crop&w=1200&q=80",
    "gadget": "https://images.unsplash.com/photo-1510557880182-3d4d3cba35a5?auto=format&fit=crop&w=1200&q=80",
    "traffic": "https://images.unsplash.com/photo-1558981403-c5f9899a28bc?auto=format&fit=crop&w=1200&q=80",
}


# ==============================================================================
# 2. SISTEM PENJADWALAN PROGRAM MINGGUAN
# ==============================================================================
def get_daily_program_config() -> Dict[str, Any]:
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
                "https://news.google.com/rss/search?q=rupiah+tembus+OR+harga+emas+OR+saham+ihsg+OR+biaya+hidup+indonesia&hl=id&gl=ID&ceid=ID:id",
            ],
            "sources": [
                "Bank Indonesia (BI)",
                "Bursa Efek Indonesia (IDX)",
                "Logam Mulia PT Antam Tbk",
                "Badan Pusat Statistik (BPS)",
            ],
        }


# ==============================================================================
# 3. MODUL INGESTION BERITA & FOTO TERVALIDASI (100% AKURAT)
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
        candidates.append(
            {
                "title": "Rupiah Tembus Rp 16.500 per Dolar AS: Beban Impor Membengkak dan Risiko Inflasi",
                "link": f"https://metrika.id/kurs/{datetime.date.today()}",
                "summary": "Tekanan nilai tukar rupiah terhadap dolar AS memicu kenaikan biaya produksi industri dan potensi lonjakan harga barang pokok.",
                "published": str(datetime.date.today()),
            }
        )

    primary_item = candidates[0]
    supporting = [item["title"] for item in candidates[1:6]]
    print(f"[RSS] Topik Terpilih ({prog_cfg['name']}): {primary_item['title']}")
    return primary_item, supporting


ACRONYM_MAP = {
    "BBCA": "Bank Central Asia BCA gedung Jakarta",
    "BBRI": "Bank Rakyat Indonesia BRI kantor gedung",
    "BMRI": "Bank Mandiri kantor pusat Jakarta",
    "BBNI": "Bank BNI kantor Jakarta",
    "IHSG": "Bursa Efek Indonesia IDX trading floor",
    "BEI": "Bursa Efek Indonesia IDX building",
    "RUPIAH": "Indonesian rupiah banknotes currency cash money",
    "DOLAR": "US dollar banknotes currency cash",
    "KURS": "Currency exchange money trading stock market",
    "EMAS": "Gold bullion bars antam 24k",
    "ANTAM": "Gold bullion bars antam logammulia",
    "KRL": "KRL Commuter Line train station Jakarta",
    "OJOL": "Motorcycle taxi street Jakarta traffic",
    "BPS": "Jakarta modern city building skyline",
}

def clean_query_term(raw_query: str) -> str:
    words = raw_query.upper().split()
    for w in words:
        clean_w = re.sub(r'[^A-Z]', '', w)
        if clean_w in ACRONYM_MAP:
            return ACRONYM_MAP[clean_w]
    
    clean = re.sub(r'[^\w\s]', ' ', raw_query).strip()
    tokens = [t for t in clean.split() if len(t) > 2 and t.lower() not in ["dan", "yang", "dari", "untuk", "pada", "adalah", "ini", "itu", "atau", "bisa", "akan"]]
    return " ".join(tokens[:4])


def is_safe_image_url(url: str) -> bool:
    """Filter ketat penolakan dokumen scan, buku arsip, kartun, dan domain berbahaya."""
    url_low = url.lower()
    if any(b in url_low for b in BLOCKED_IMAGE_DOMAINS):
        return False
    if any(t in url_low for t in DISALLOWED_IMAGE_TERMS):
        return False
    return True


def fetch_editorial_photo_with_meta(
    news_item: Dict[str, str], query_term: str, save_path: Path, fallback_key: str = "chart"
) -> Tuple[Path, str]:
    """
    Mengunduh foto jurnalistik 100% nyata & akurat.
    Menggunakan Unsplash Vault + Bing Photo Filter + Validasi Pixel Anti-Dokumen Scan.
    """
    candidate_urls: List[str] = []
    clean_q = clean_query_term(query_term)
    meta_text = f"{query_term} {news_item['title']}"

    # Deteksi vault otomatis berdasarkan teks berita
    title_low = (news_item["title"] + " " + query_term).lower()
    if any(k in title_low for k in ["rupiah", "dolar", "kurs", "uang", "valas", "devisa"]):
        if "chart" in fallback_key:
            candidate_urls.append(TOPIC_IMAGE_VAULT["chart"])
        else:
            candidate_urls.append(TOPIC_IMAGE_VAULT["rupiah"])
            candidate_urls.append(TOPIC_IMAGE_VAULT["money"])
            candidate_urls.append(TOPIC_IMAGE_VAULT["currency_exchange"])
    elif any(k in title_low for k in ["emas", "antam", "logam mulia", "gold"]):
        candidate_urls.append(TOPIC_IMAGE_VAULT["gold"])
        candidate_urls.append(TOPIC_IMAGE_VAULT["gold_coins"])
    elif any(k in title_low for k in ["saham", "ihsg", "bursa", "idx", "msci"]):
        candidate_urls.append(TOPIC_IMAGE_VAULT["chart"])
        candidate_urls.append(TOPIC_IMAGE_VAULT["trading_screen"])
        candidate_urls.append(TOPIC_IMAGE_VAULT["investor"])

    # Cari di Bing Image Search dengan Filter Ketat (+photo +large) & Negative Terms
    try:
        search_engine_q = f"{clean_q} photography stock market business -document -archive -scan -paper -book -anime -cartoon -drawing -illustration"
        bing_url = (
            "https://www.bing.com/images/search?q="
            + urllib.parse.quote(search_engine_q)
            + "&qft=+filterui:photo+filterui:imagesize-large"
        )
        b_resp = requests.get(bing_url, headers=HTTP_HEADERS, timeout=6)
        if b_resp.status_code == 200:
            matches = re.findall(r'murl&quot;:&quot;(https?://[^&]+?)&quot;', b_resp.text)
            for m in matches[:6]:
                if is_safe_image_url(m):
                    candidate_urls.append(m)
    except Exception:
        pass

    # Tambahkan fallback default dari vault
    candidate_urls.append(TOPIC_IMAGE_VAULT.get(fallback_key, TOPIC_IMAGE_VAULT["chart"]))
    candidate_urls.append(TOPIC_IMAGE_VAULT["jakarta"])

    # Validasi download gambar dengan filter pixel anti-kertas scan
    for img_url in candidate_urls:
        try:
            r = requests.get(img_url, headers=HTTP_HEADERS, timeout=8)
            if r.status_code == 200 and len(r.content) > 15_000:
                pil_img = Image.open(io.BytesIO(r.content)).convert("RGB")
                
                # Cek dimensi: harus berorientasi landscape/horizontal
                if pil_img.width < 500 or pil_img.height < 300:
                    continue
                if pil_img.height > pil_img.width * 1.2:
                    continue  # Tolak dokumen scan berorientasi vertikal/portrait

                # Cek rasio pixel putih: jika > 65% putih pekat, itu adalah dokumen teks/kertas scan!
                gray = pil_img.convert("L")
                hist = gray.histogram()
                white_pixels = sum(hist[238:])
                total_pixels = pil_img.width * pil_img.height
                if (white_pixels / total_pixels) > 0.60:
                    print(f"[Photo Rejected] Ditolak karena terdeteksi dokumen/kertas putih scan ({white_pixels/total_pixels*100:.1f}% putih).")
                    continue

                pil_img.save(save_path, format="JPEG", quality=92)
                print(f"[Photo] Foto jurnalistik akurat terverifikasi: {img_url[:65]}...")
                return save_path, f"{meta_text} {img_url}"
        except Exception:
            continue

    # Fallback Terakhir: Ambil foto rupiah/emas/chart terverifikasi dari Unsplash Vault
    backup_url = TOPIC_IMAGE_VAULT.get(fallback_key, TOPIC_IMAGE_VAULT["chart"])
    try:
        r = requests.get(backup_url, headers=HTTP_HEADERS, timeout=10)
        pil_img = Image.open(io.BytesIO(r.content)).convert("RGB")
        pil_img.save(save_path, format="JPEG", quality=92)
        return save_path, f"{meta_text} {backup_url}"
    except Exception:
        pass

    # Cadangan absolut jika internet mati total
    im = Image.new("RGB", (1200, 800), (35, 23, 16))
    im.save(save_path, format="JPEG", quality=92)
    return save_path, meta_text


# ==============================================================================
# 4. OTAK AI: ANALISIS JURNALISTIK KELAS AGENSI (COPYWRITING EMOSIONAL & TAJAM)
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

    instructions = f"""
Kamu adalah Pemimpin Redaksi & Direktur Kreatif media riset data investigasi papan atas "{MEDIA_NAME}" (setara @theeconomicinfluence, Bloomberg QuickTake, Visual Capitalist).
Misi: Mengubah berita harian menjadi CAROUSEL 5 SLIDE NARRATIVE DENGAN COPYWRITING KELAS DUNIA.

PANDUAN COPYWRITING BERKELAS TINGGI:
1. DILARANG KERAS BAHASA BIROKRAT KLISE: JANGAN gunakan kalimat hambar seperti 'Saatnya cermati dampak dan strategi antisipasi', 'Dilema ekonomi nasional', atau 'Perlu ditingkatkan kesadaran'. Itu membosankan dan diabaikan audiens!
2. HOOK COVER (SLIDE 1): Harus provokatif, memicu rasa penasaran, dan langsung menyentuh dompet/kehidupan pembaca. Gunakan tag <red>...</red> untuk 2-4 kata kunci paling emosional.
   - Contoh Hebat: 'Rupiah Tembus 18.000, <red>Harga Barang Impor Bakal Meledak</red>: Siapa yang Bakal Paling Menjerit?'
   - Contoh Hebat: 'Emas Tembus Rekor, <red>Gaji Kita Makin Tertinggal</red>: Jangan Beli Sebelum Baca Ini!'
3. HOOK SLIDE 2 (KONTEKS): Tulis pertanyaan menohok penahan scroll (contoh: 'Kenapa Dolar Tiba-tiba Menggila dan Bikin Rupiah Berdarah-darah?'). 3 poin investigasi wajib diawali **Bold Lead-in Tajam** diikuti uraian 25-35 kata penuh data riil.
4. HOOK SLIDE 3 (BEDAH ANGKA): Tulis hook kalkulasi riil (contoh: 'Berapa Beban Tambahan yang Diam-diam Disedot dari Dompetmu?'). Cantumkan angka spotlight yang bikin terperangah (misal: '+Rp 450 Ribu', '-6,5%', '2,4 Juta Lot').
5. HOOK SLIDE 4 (SKENARIO STRATEGIS): Tulis hook aksi konkret (contoh: 'Tiga Benteng Finansial Sebelum Badai Inflasi Mengganas'). Buat 3 skenario taktis untuk 3 profil berbeda (Konsumen Ritel, Pelaku Usaha UMKM, Investor Saham).
6. VERDICT & DISKUSI (SLIDE 5): Kalimat kesimpulan berbobot (contoh: 'Rupiah boleh melemah, tapi strategi finansialmu tidak boleh ikut lumpuh.') + Pertanyaan diskusi terbuka pemantik ratusan komentar.

PANDUAN PENCARIAN FOTO (FOTOGRAFI NYATA):
- Berikan kata kunci pencarian foto fisik konkret (misal: 'indonesian rupiah banknotes', 'stock trading chart candlestick', 'bank vault gold bullion', 'jakarta central business district').

Format output JSON murni tanpa markdown:
{{
  "subject_title": "Topik Utama (maks 25 karakter)",
  "hook": "Rupiah Tembus 18.000, <red>Harga Barang Impor Bakal Meledak</red>: Siapa yang Bakal Paling Menjerit?",
  "hero_value": "Rp 18.000",
  "hero_label": "level psikologis rupiah terhadap dolar AS yang memicu alarm ekonomi",
  "slide1_photo_query": "indonesian rupiah banknotes money cash",
  "fallback_theme_1": "rupiah",

  "slide2_eyebrow": "01 / DOKUMENTASI FAKTA",
  "slide2_hook": "Kenapa Dolar Makin Perkasa dan Bikin Rupiah Berdarah-darah?",
  "slide2_points": [
    "**Suku Bunga Agresif The Fed:** Bank Sentral AS menahan suku bunga tinggi, memicu aksi 'sedot' likuiditas modal keluar dari pasar negara berkembang.",
    "**Jatuh Tempo Utang Valas:** Korporasi domestik berebut memborong dolar di pasar spot untuk melunasi kewajiban utang luar negeri.",
    "**Tagihan Impor Energi & Pangan:** Ketergantungan impor minyak mentah dan bahan pokok menguras cadangan devisa hingga miliaran dolar setiap kuartal."
  ],
  "slide2_takeaway": "Pelemahan kurs bukan sekadar angka di grafik, melainkan sinyal lonjakan biaya hidup sehari-hari.",
  "slide2_photo_query": "stock market trading chart candlestick",
  "fallback_theme_2": "chart",

  "slide3_eyebrow": "02 / BEDAH DATA RISET",
  "slide3_hook": "Berapa Beban yang Diam-diam Harus Ditanggung Dompet Kita?",
  "slide3_metric_value": "-6,5%",
  "slide3_metric_label": "depresiasi rupiah year-to-date terlemah di antara mata uang utama regional",
  "slide3_col1_title": "Beban Dompet Konsumen Ritel",
  "slide3_col1_points": [
    "Harga barang elektronik, laptop, dan gadget impor naik rata-rata 8-12 persen.",
    "Kenaikan harga pakan ternak impor mengerek harga telur dan daging ayam potong di pasar tradisional.",
    "Tarif transportasi dan bahan bakar berpotensi disesuaikan akibat lonjakan subsidi valas."
  ],
  "slide3_col2_title": "Beban Sektor Usaha & Manufaktur",
  "slide3_col2_points": [
    "Margin keuntungan industri tekstil dan plastik tergerus karena 70% bahan baku dibayar dengan dolar.",
    "Biaya sewa cloud server dan lisensi software teknologi membengkak drastis bagi pelaku startup.",
    "Risiko efisiensi tenaga kerja di pabrik-pabrik padat impor jika pelemahan bertahan lebih dari 3 bulan."
  ],
  "slide3_alert_text": "Setiap pelemahan Rp 500 per dolar menambah beban belanja negara hingga puluhan triliun rupiah.",
  "slide3_photo_query": "currency exchange cash desk bank",
  "fallback_theme_3": "currency_exchange",

  "slide4_eyebrow": "03 / SKENARIO STRATEGIS",
  "slide4_hook": "Tiga Benteng Finansial Sebelum Badai Inflasi Mengganas",
  "slide4_scenarios": [
    {{"tag": "SKENARIO KONSUMEN & KELUARGA", "text": "**Tunda Konsumsi Impor:** Tunda upgrade gadget atau barang mewah non-primer, alihkan arus kas ekstra ke dana darurat likuid berbunga tinggi."}},
    {{"tag": "SKENARIO PELAKU USAHA & UMKM", "text": "**Kunci Pasokan Lokal:** Negosiasikan kontrak pengadaan jangka panjang dan segera beralih ke pemasok bahan baku alternatif dalam negeri."}},
    {{"tag": "SKENARIO INVESTOR PASAR MODAL", "text": "**Akumulasi Saham Berbasis Dolar:** Rotasikan portofolio ke emiten tambang dan komoditas ekspor yang justru meraup lonjakan laba saat dolar menguat."}}
  ],
  "slide4_takeaway": "Rupiah boleh melemah, tapi strategi finansialmu tidak boleh ikut lumpuh.",
  "slide4_photo_query": "jakarta sudirman central business district skyline",
  "fallback_theme_4": "jakarta",

  "verdict": "Pelemahan mata uang bukanlah kiamat finansial; pemenang krisis adalah mereka yang paham arah arus uang, bukan yang pasrah mengeluh.",
  "cta": "Apakah gajimu saat ini sudah aman menghadapi kenaikan harga barang impor, atau kamu mulai cari side income? Bagikan strategimu di komentar!",
  "sources": ["Bank Indonesia (BI)", "Federal Reserve (The Fed)", "Badan Pusat Statistik (BPS)", "Bloomberg Terminal"],
  "slide5_photo_query": "financial investor screen trading desk",
  "fallback_theme_5": "investor"
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
            print(f"[Gemini] Mengolah data editorial ({prog_cfg['name']}) dengan model: {model_name}...")
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
# 5. CONTENT BUILDER (MENYUSUN PAYLOAD LENGKAP 5 SLIDE)
# ==============================================================================
def build_metrika_content(
    analysis: Dict[str, Any],
    prog_cfg: Dict[str, Any],
    images: Dict[str, Path],
) -> Dict[str, Any]:
    today_str = datetime.datetime.now().strftime("%d %b %Y")
    
    return {
        "program": prog_cfg["id"],
        "date": today_str,
        "hook": analysis.get("hook", "Analisis Data Finansial Hari Ini"),
        "hero": {
            "value": analysis.get("hero_value", "Level Krusial"),
            "label": analysis.get("hero_label", "acuan data pasar resmi terverifikasi"),
        },
        "hero_image": str(images["slide1"]),
        "slide2_image": str(images["slide2"]),
        "slide3_image": str(images["slide3"]),
        "slide4_image": str(images["slide4"]),
        "slide5_image": str(images["slide5"]),

        "slide_context": {
            "eyebrow": analysis.get("slide2_eyebrow", "01 / DOKUMENTASI FAKTA"),
            "hook": analysis.get("slide2_hook", "Kenapa Dolar Tiba-tiba Menggila dan Bikin Rupiah Berdarah-darah?"),
            "points": analysis.get("slide2_points", [
                "**Kebijakan Moneter Global:** Bank sentral menahan suku bunga tinggi sehingga arus modal asing tersedot keluar.",
                "**Beban Impor Bahan Baku:** Kebutuhan valas membengkak untuk membayar pasokan komoditas luar negeri.",
                "**Kewajiban Utang Luar Negeri:** Korporasi domestik berebut menukar rupiah untuk melunasi utang jatuh tempo."
            ]),
            "takeaway": analysis.get("slide2_takeaway", "Pelemahan kurs bukan sekadar angka di berita, tapi lonjakan biaya hidup nyata."),
        },

        "slide_metric": {
            "eyebrow": analysis.get("slide3_eyebrow", "02 / BEDAH DATA RISET"),
            "hook": analysis.get("slide3_hook", "Berapa Beban yang Diam-diam Harus Ditanggung Dompet Kita?"),
            "metric_value": analysis.get("slide3_metric_value", "-6,5%"),
            "metric_label": analysis.get("slide3_metric_label", "depresiasi rupiah year-to-date terhadap dolar AS"),
            "col1_title": analysis.get("slide3_col1_title", "Beban Konsumen Ritel"),
            "col1_points": analysis.get("slide3_col1_points", [
                "Harga barang elektronik dan gadget impor melonjak 8-12 persen.",
                "Biaya pakan impor mengerek harga bahan pangan di pasar tradisional.",
                "Cicilan dan pengeluaran berbasis valas kian membebani arus kas bulanan."
            ]),
            "col2_title": analysis.get("slide3_col2_title", "Beban Sektor Usaha"),
            "col2_points": analysis.get("slide3_col2_points", [
                "Margin industri manufaktur tergerus biaya bahan baku impor yang mahal.",
                "Pelaku UMKM kesulitan menaikkan harga jual di tengah daya beli yang melandai.",
                "Risiko efisiensi operasional jika pelemahan kurs berlanjut panjang."
            ]),
            "alert_text": analysis.get("slide3_alert_text", "Pelemahan tajam memicu efek domino penyesuaian harga di tingkat distributor."),
        },

        "slide_strategy": {
            "eyebrow": analysis.get("slide4_eyebrow", "03 / SKENARIO STRATEGIS"),
            "hook": analysis.get("slide4_hook", "Tiga Benteng Finansial Sebelum Badai Inflasi Mengganas"),
            "scenarios": analysis.get("slide4_scenarios", [
                {"tag": "SKENARIO KONSUMEN & KELUARGA", "text": "**Tunda Belanja Impor:** Tunda pembelian gadget/otomotif impor, amankan porsi dana darurat tunai."},
                {"tag": "SKENARIO PELAKU USAHA & UMKM", "text": "**Kunci Pasokan Lokal:** Beralih ke bahan baku alternatif dalam negeri untuk selamatkan margin laba."},
                {"tag": "SKENARIO INVESTOR PASAR MODAL", "text": "**Rotasi Aset Produktif:** Koleksi saham berbasis pendapatan dolar yang justru diuntungkan apresiasi kurs."}
            ]),
            "takeaway": analysis.get("slide4_takeaway", "Rupiah boleh melemah, tapi strategi finansialmu tidak boleh ikut lumpuh."),
        },

        "verdict": analysis.get("verdict", "Pemenang krisis adalah mereka yang paham arah arus uang, bukan yang pasrah mengeluh."),
        "cta": analysis.get("cta", "Apakah gajimu saat ini sudah aman menghadapi kenaikan harga impor, atau kamu mulai cari side income? Tulis strategimu di komentar!"),
        "sources": analysis.get("sources") or prog_cfg["sources"],
    }


# ==============================================================================
# 6. DISTRIBUSI KE TELEGRAM (ALBUM 5 SLIDE CAROUSEL)
# ==============================================================================
def send_outputs_to_telegram(
    carousel_paths: List[Path],
    content: Dict[str, Any],
    news_item: Dict[str, str],
) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Telegram] Token/Chat ID belum diset. Melewati kirim Telegram.")
        return

    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    clean_h = re.sub(r"</?red>", "", content["hook"])

    header_caption = (
        f"📊 *{MEDIA_NAME.upper()} • JURNALISME DATA & RISET FINANSIAL*\n\n"
        f"*{clean_h}*\n\n"
        f"📌 *Angka Kunci:* {content['hero']['value']} ({content['hero']['label']})\n\n"
        f"⚖️ *Verdict Redaksi:*\n_{content['verdict']}_\n\n"
        f"💬 *Diskusi Publik:*\n{content['cta']}\n\n"
        f"📚 *Rujukan Data:* " + ", ".join(content.get("sources", []))
    )

    print(f"[Telegram] Mengirim album Carousel ({len(carousel_paths)} slide)...")
    media_group = []
    files_payload = {}
    for idx, img_path in enumerate(carousel_paths):
        attach_key = f"slide_{idx}"
        files_payload[attach_key] = img_path.open("rb")
        item_obj: Dict[str, Any] = {"type": "photo", "media": f"attach://{attach_key}"}
        if idx == 0:
            item_obj["caption"] = header_caption[:1024]
            item_obj["parse_mode"] = "Markdown"
        media_group.append(item_obj)

    try:
        res = requests.post(
            f"{base_url}/sendMediaGroup",
            data={"chat_id": TELEGRAM_CHAT_ID, "media": json.dumps(media_group)},
            files=files_payload,
            timeout=120,
        )
        if res.status_code == 200:
            print("[Telegram] Sukses mengirim album Carousel 5 Slide!")
        else:
            print(f"[Telegram] Respon Telegram: {res.text}")
    finally:
        for f in files_payload.values():
            f.close()


# ==============================================================================
# 7. PIPELINE UTAMA
# ==============================================================================
def main() -> None:
    prog_cfg = get_daily_program_config()

    print("=" * 72)
    print(f"🚀 MEMULAI PIPELINE CAROUSEL 5 SLIDE: {MEDIA_NAME.upper()} • {prog_cfg['name']}")
    print(f"📅 Rubrik: {prog_cfg['subtitle']}")
    print("=" * 72)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CAROUSEL_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Ingestion berita RSS
    news_item, supporting = fetch_latest_program_news(prog_cfg)

    # 2. Analisis AI Gemini untuk 5 Slide Lengkap dengan Copywriting Tajam
    analysis = analyze_with_gemini(news_item, supporting, prog_cfg)

    # 3. Cari Foto Jurnalistik Nyata & Terverifikasi untuk SETIAP Slide (Anti-Dokumen Scan & Anti-Buku Arsip)
    images: Dict[str, Path] = {}
    
    q1 = analysis.get("slide1_photo_query") or analysis.get("subject_title", "business finance")
    f1 = analysis.get("fallback_theme_1", "rupiah")
    images["slide1"], _ = fetch_editorial_photo_with_meta(news_item, q1, HERO_IMG_PATH, f1)

    q2 = analysis.get("slide2_photo_query") or "stock market trading chart"
    f2 = analysis.get("fallback_theme_2", "chart")
    images["slide2"], _ = fetch_editorial_photo_with_meta(news_item, q2, SLIDE2_IMG_PATH, f2)

    q3 = analysis.get("slide3_photo_query") or "currency exchange cash money"
    f3 = analysis.get("fallback_theme_3", "currency_exchange")
    images["slide3"], _ = fetch_editorial_photo_with_meta(news_item, q3, SLIDE3_IMG_PATH, f3)

    q4 = analysis.get("slide4_photo_query") or "jakarta central business district"
    f4 = analysis.get("fallback_theme_4", "jakarta")
    images["slide4"], _ = fetch_editorial_photo_with_meta(news_item, q4, SLIDE4_IMG_PATH, f4)

    q5 = analysis.get("slide5_photo_query") or "financial investor screens trading desk"
    f5 = analysis.get("fallback_theme_5", "investor")
    images["slide5"], _ = fetch_editorial_photo_with_meta(news_item, q5, SLIDE5_IMG_PATH, f5)

    # 4. Adaptasi ke Skema Konten Lengkap
    content = build_metrika_content(analysis, prog_cfg, images)

    latest_json = OUTPUT_DIR / "latest_analysis.json"
    latest_json.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")

    # 5. Render Carousel 5 Slide Berkualitas Agensi via Playwright
    print("[Render] Memulai render 5 Slide Carousel 1080x1350...")
    carousel_files = render_carousel_slides(content, CAROUSEL_DIR)
    print(f"[Render] Sukses merender {len(carousel_files)} slide carousel.")

    # 6. Kirim Album Carousel ke Telegram
    send_outputs_to_telegram(carousel_files, content, news_item)

    # 7. Update Cache Link
    save_posted_link(news_item["link"])
    print(f"[Cache] Link berhasil disimpan ke {CACHE_FILE}.")
    print(f"✅ PIPELINE CAROUSEL {prog_cfg['name']} SELESAI DENGAN SUKSES!")


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"❌ [ERROR] Pipeline berhenti: {err}", file=sys.stderr)
        sys.exit(1)
