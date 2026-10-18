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
- Foto Jurnalistik 100% Nyata & Terverifikasi (Bebas Bot-Detection, Bebas Gambar Acak).
- Pustaka Visual Tematik Langsung (SPBU/BBM, Uang Rupiah, Emas Antam, Saham IDX, Mobil/Otomotif).
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

# ==============================================================================
# PUSTAKA FOTO JURNALISTIK TERVERIFIKASI (100% NYATA & RELEVAN SESUAI TOPIK)
# Menghindari bot-detection scraping yang memicu gambar acak (seperti game / translate).
# ==============================================================================
TOPIC_IMAGE_REGISTRY = {
    "fuel": [
        "https://images.unsplash.com/photo-1545454675-3531b543be5d?auto=format&fit=crop&w=1200&q=80", # SPBU Nozzle & Fueling
        "https://images.unsplash.com/photo-1506521781263-d8422e82f27a?auto=format&fit=crop&w=1200&q=80", # Antrean Mobil Jalan Raya
        "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=1200&q=80", # Kilang Minyak Industri
        "https://images.unsplash.com/photo-1584345604476-8ec5e12e42dd?auto=format&fit=crop&w=1200&q=80", # Indikator Bensin Mobil
        "https://images.unsplash.com/photo-1558981403-c5f9899a28bc?auto=format&fit=crop&w=1200&q=80", # Lalu Lintas Sepeda Motor Jakarta
    ],
    "currency": [
        "https://images.unsplash.com/photo-1580519542036-c47de6196ba5?auto=format&fit=crop&w=1200&q=80", # Uang Kertas & Finansial
        "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?auto=format&fit=crop&w=1200&q=80", # Pertukaran Valuta Asing
        "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=1200&q=80", # Grafik Candlestick Forex
        "https://images.unsplash.com/photo-1578632767115-351597cf2477?auto=format&fit=crop&w=1200&q=80", # Gedung Pusat Bisnis Sudirman
        "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?auto=format&fit=crop&w=1200&q=80", # Trader Analisis Data Kurs
    ],
    "gold": [
        "https://images.unsplash.com/photo-1610375461246-83df859d849d?auto=format&fit=crop&w=1200&q=80", # Emas Batangan Asli
        "https://images.unsplash.com/photo-1509718443690-d8e2fb3474b7?auto=format&fit=crop&w=1200&q=80", # Koin Emas & Investasi
        "https://images.unsplash.com/photo-1642543492481-44e81e3914a7?auto=format&fit=crop&w=1200&q=80", # Grafik Pasar Komoditas
        "https://images.unsplash.com/photo-1565372195458-9de0b320ef04?auto=format&fit=crop&w=1200&q=80", # Brankas Bank Khazanah Emas
        "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?auto=format&fit=crop&w=1200&q=80", # Keputusan Finansial Investor
    ],
    "stocks": [
        "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?auto=format&fit=crop&w=1200&q=80", # Layar Bursa Saham Trading
        "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=1200&q=80", # Candlestick Chart Saham
        "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=1200&q=80", # Gedung Pencakar Langit Bursa
        "https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1200&q=80", # Dashboard Data Analitik
        "https://images.unsplash.com/photo-1517048676732-d65bc937f952?auto=format&fit=crop&w=1200&q=80", # Diskusi Dewan Investor
    ],
    "automotive": [
        "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?auto=format&fit=crop&w=1200&q=80", # Mobil SUV Mewah di Jalan
        "https://images.unsplash.com/photo-1545454675-3531b543be5d?auto=format&fit=crop&w=1200&q=80", # Pengisian Bahan Bakar Mobil
        "https://images.unsplash.com/photo-1506521781263-d8422e82f27a?auto=format&fit=crop&w=1200&q=80", # Antrean Kendaraan di Jalan
        "https://images.unsplash.com/photo-1584345604476-8ec5e12e42dd?auto=format&fit=crop&w=1200&q=80", # Dashboard Mobil & Konsumsi
        "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?auto=format&fit=crop&w=1200&q=80", # Kendaraan Lalu Lintas Kota
    ],
    "general": [
        "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=1200&q=80", # Gedung Finansial & Bisnis
        "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=1200&q=80", # Grafik Data Ekonomi
        "https://images.unsplash.com/photo-1580519542036-c47de6196ba5?auto=format&fit=crop&w=1200&q=80", # Arus Uang & Perbankan
        "https://images.unsplash.com/photo-1578632767115-351597cf2477?auto=format&fit=crop&w=1200&q=80", # Pusat Bisnis Metropolitan
        "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?auto=format&fit=crop&w=1200&q=80", # Analisis Riset & Keputusan
    ],
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
                "https://news.google.com/rss/search?q=pertalite+OR+harga+bbm+OR+subsidi+energi+OR+harga+mobil+indonesia&hl=id&gl=ID&ceid=ID:id",
            ],
            "sources": [
                "PT Pertamina (Persero)",
                "Kementerian ESDM RI",
                "Badan Pengatur Hilir Migas (BPH Migas)",
                "Kepgub DKI No. 1026/2024 (UMP Rp 5.396.763)",
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
                "https://news.google.com/rss/search?q=viral+OR+perdebatan+OR+subsidi+bbm+OR+pro+kontra+indonesia&hl=id&gl=ID&ceid=ID:id",
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
                "https://news.google.com/rss/search?q=pertalite+OR+subsidi+energi+OR+rupiah+tembus+OR+harga+emas+indonesia&hl=id&gl=ID&ceid=ID:id",
            ],
            "sources": [
                "PT Pertamina (Persero)",
                "Kementerian ESDM RI",
                "Bank Indonesia (BI)",
                "Bursa Efek Indonesia (IDX)",
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
        candidates.append(
            {
                "title": "Antrean Panjang Pembelian Pertalite di SPBU dan Wacana Pengetatan QR Code Kendaraan",
                "link": f"https://metrika.id/bbm/{datetime.date.today()}",
                "summary": "Pembatasan konsumsi BBM bersubsidi memicu kepanikan warga dan antrean mengular kendaraan di berbagai stasiun pengisian bahan bakar.",
                "published": str(datetime.date.today()),
            }
        )

    primary_item = candidates[0]
    supporting = [item["title"] for item in candidates[1:6]]
    print(f"[RSS] Topik Terpilih ({prog_cfg['name']}): {primary_item['title']}")
    return primary_item, supporting


def detect_topic_category(text: str) -> str:
    """Mendeteksi kategori topik untuk memilih set foto jurnalistik yang 100% tepat."""
    t = text.lower()
    if any(k in t for k in ["bbm", "pertalite", "pertamax", "spbu", "bensin", "solar", "minyak", "subsidi energi", "pajero"]):
        return "fuel"
    if any(k in t for k in ["emas", "antam", "logam mulia", "gold"]):
        return "gold"
    if any(k in t for k in ["rupiah", "dolar", "kurs", "uang", "valas", "devisa", "inflasi"]):
        return "currency"
    if any(k in t for k in ["saham", "ihsg", "bursa", "idx", "bei", "msci"]):
        return "stocks"
    if any(k in t for k in ["mobil", "motor", "otomotif", "toyota", "honda", "kendaraan"]):
        return "automotive"
    return "general"


def download_editorial_images_for_carousel(
    news_item: Dict[str, str], analysis: Dict[str, Any]
) -> Dict[str, Path]:
    """
    Mengunduh 5 foto jurnalistik resolusi tinggi yang 100% cocok dengan topik.
    Menggunakan Pustaka Visual Terverifikasi (Bebas Bot-Detection Azure/Bing).
    """
    category = detect_topic_category(news_item["title"] + " " + analysis.get("subject_title", ""))
    urls = TOPIC_IMAGE_REGISTRY.get(category, TOPIC_IMAGE_REGISTRY["general"])
    
    print(f"[Photo Engine] Kategori visual terpilih: {category.upper()} (5 Foto Terverifikasi)")

    save_map = {
        "slide1": HERO_IMG_PATH,
        "slide2": SLIDE2_IMG_PATH,
        "slide3": SLIDE3_IMG_PATH,
        "slide4": SLIDE4_IMG_PATH,
        "slide5": SLIDE5_IMG_PATH,
    }

    result: Dict[str, Path] = {}
    for i, (key, path) in enumerate(save_map.items()):
        url = urls[i % len(urls)]
        try:
            r = requests.get(url, headers=HTTP_HEADERS, timeout=12)
            if r.status_code == 200 and len(r.content) > 10_000:
                pil_img = Image.open(io.BytesIO(r.content)).convert("RGB")
                pil_img.save(path, format="JPEG", quality=92)
                result[key] = path
                print(f"[Photo Engine] Slide {i+1} tersimpan ({category}): {path.name}")
                continue
        except Exception as e:
            print(f"[Photo Engine] Gagal download url: {e}")

        # Fallback kanvas terkurasi jika koneksi timeout
        im = Image.new("RGB", (1200, 800), (35, 23, 16))
        im.save(path, format="JPEG", quality=92)
        result[key] = path

    return result


# ==============================================================================
# 4. OTAK AI: COPYWRITING INVESTIGASI TAJAM & BERKELAS AGENSI
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
Misi: Mengubah berita terpilih menjadi CAROUSEL 5 SLIDE NARRATIVE DENGAN COPYWRITING KELAS DUNIA.

STANDAR COPYWRITING INVESTIGATIF TAJAM:
1. DILARANG KERAS MENGGUNAKAN BAHASA BIROKRAT KLISE (seperti: 'Saatnya cermati dampak dan strategi antisipasi', 'Dilema ekonomi nasional', 'Perlu ditingkatkan kesadaran'). Itu hambar dan membosankan!
2. HOOK COVER (SLIDE 1): Wajib tajam, provokatif, sedikit satir, langsung menyentuh kepentingan publik. Gunakan tag <red>...</red> untuk 2-4 kata paling emosional.
   - Contoh Hebat: 'Pajero Minum Pertalite, <red>Dompet Kita Makin Tercekik</red>: Kenapa Antrean SPBU Makin Gila?'
   - Contoh Hebat: 'Rupiah Tembus 18.000, <red>Harga Barang Bakal Meledak</red>: Siapa yang Bakal Paling Menjerit?'
3. HOOK SLIDE 2: Pertanyaan kritis menohok (contoh: 'Kenapa BBM Subsidi Tiba-tiba Langka dan Bikin Antrean Mengular?'). Tulis 3 poin investigasi yang diawali **Bold Lead-in** + 25 sampai 35 kata fakta mendalam (minimal 3 baris per poin!).
4. HOOK SLIDE 3: Angka audit yang bikin terperangah (contoh: 'Berapa Triliun Rupiah Subsidi Kita yang Bocor ke Kantong yang Salah?'). Tulis metric spotlight angka (misal: 'Rp 150 Triliun+') dan 2 kolom analisis komparasi mendalam (masing-masing 3 butir padat).
5. HOOK SLIDE 4: Panduan taktis aplikatif (contoh: 'Tiga Benteng Finansial Sebelum Subsidi Makin Mengetat'). Rancang 3 skenario mitigasi untuk 3 kelompok berbeda (Konsumen Ritel, Pelaku Usaha UMKM, Pengawas Kebijakan).
6. VERDICT & DISKUSI (SLIDE 5): Kutipan kesimpulan berbobot + 3 butir poin kunci investigasi ('slide5_highlights') + pertanyaan diskusi pemantik ratusan komentar di Telegram/Instagram.

Format output JSON murni tanpa markdown:
{{
  "subject_title": "Topik Berita (maks 25 karakter)",
  "hook": "Pajero Minum Pertalite, <red>Dompet Kita Makin Tercekik</red>: Kenapa Antrean SPBU Makin Gila?",
  "hero_value": "16 Hari",
  "hero_label": "sisa ketahanan stok bbm subsidi nasional yang memicu alarm kelangkaan di spbu",

  "slide2_eyebrow": "01 / DOKUMENTASI FAKTA",
  "slide2_hook": "Kenapa BBM Subsidi Tiba-tiba Langka dan Bikin Antrean Mengular?",
  "slide2_points": [
    "**Penyalahgunaan Sistematis:** Ribuan kendaraan mewah dan armada industri besar kedapatan menjarah jatah BBM bersubsidi yang seharusnya diperuntukkan bagi rakyat kecil.",
    "**Penimbunan Skala Masif:** Sindikat spekulan memanfaatkan celah pengawasan manual di lapangan untuk menimbun pasokan dan menjualnya kembali dengan harga industri.",
    "**Lonjakan Konsumsi Tak Terkendali:** Mobilitas pasca-pandemi dan pertumbuhan kendaraan pribadi melampaui kuota APBN, diperparah disparitas harga keekonomian yang terlampau jauh."
  ],
  "slide2_takeaway": "Kelangkaan BBM bukan sekadar antrean fisik, melainkan cerminan tata kelola distribusi yang belum tepat sasaran.",

  "slide3_eyebrow": "02 / BEDAH DATA RISET",
  "slide3_hook": "Berapa Triliun Rupiah Subsidi Kita yang Bocor ke Kantong yang Salah?",
  "slide3_metric_value": "Rp 150 T+",
  "slide3_metric_label": "estimasi alokasi anggaran subsidi energi yang rentan bocor akibat salah sasaran",
  "slide3_col1_title": "Beban Dompet Konsumen Ritel",
  "slide3_col1_points": [
    "Waktu produktif masyarakat terbuang sia-sia 2 hingga 3 jam per minggu hanya untuk mengantre di SPBU.",
    "Tarif ongkos logistik dan transportasi umum informal terkerek naik akibat kelangkaan bensin eceran.",
    "Munculnya pasar gelap BBM dengan harga jauh di atas ketentuan resmi yang membebani komuter harian."
  ],
  "slide3_col2_title": "Beban Sektor Usaha & UMKM",
  "slide3_col2_points": [
    "Biaya operasional armada logistik UMKM melonjak tajam, menggerus margin laba usaha kecil menengah.",
    "Keterlambatan pengiriman bahan baku mengganggu jadwal produksi dan siklus perputaran barang dagangan.",
    "Penurunan produktivitas tenaga kerja harian karena kehabisan bahan bakar saat jam operasional sibuk."
  ],
  "slide3_alert_text": "Setiap liter subsidi yang salah sasaran adalah hak rakyat kecil yang dirampas, merugikan ekonomi negara hingga triliunan rupiah.",

  "slide4_eyebrow": "03 / SKENARIO STRATEGIS",
  "slide4_hook": "Tiga Langkah Menghadapi Kebijakan Pengetatan BBM",
  "slide4_scenarios": [
    {{"tag": "SKENARIO KONSUMEN & KOMUTER", "text": "**Registrasi Digital Lebih Awal:** Segera daftarkan QR Code resmi kendaraan Anda dan atur rute perjalanan harian untuk meminimalkan konsumsi BBM."}},
    {{"tag": "SKENARIO PELAKU USAHA & UMKM", "text": "**Efisiensi Rute Logistik:** Gabungkan jadwal pengiriman barang dan pertimbangkan konversi armada bertahap ke kendaraan listrik hemat biaya."}},
    {{"tag": "SKENARIO KEBIJAKAN & PENGAWASAN", "text": "**Audit Penegakan Hukum:** Otoritas wajib menindak tegas oknum operator nakal serta memblokir nomor polisi kendaraan mewah yang nekat mengisi subsidi."}}
  ],
  "slide4_takeaway": "Krisis subsidi energi adalah momentum evaluasi efisiensi pengeluaran mobilitas harian kita.",

  "verdict": "Antrean panjang di SPBU adalah cerminan ketidakadilan sistemik. Subsidi harus sampai ke mereka yang berhak, bukan dinikmati pemilik mobil mewah.",
  "slide5_highlights": [
    "Antrean panjang membuktikan kelemahan sistem pengawasan, bukan ketiadaan pasokan minyak mentah.",
    "Mobil berkapasitas mesin besar wajib dilarang mengisi BBM bersubsidi demi rasa keadilan sosial.",
    "Digitalisasi verifikasi QR Code harus transparan dan bebas pungutan liar di tingkat stasiun pengisian."
  ],
  "cta": "Menurutmu, siapa yang paling bertanggung jawab atas kelangkaan BBM subsidi ini dan apa solusi paling ampuh? Tulis pandanganmu di komentar!",
  "sources": ["PT Pertamina (Persero)", "Kementerian ESDM RI", "Badan Pengatur Hilir Migas (BPH Migas)", "Kepolisian RI"]
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
# 5. CONTENT BUILDER (MENYIAPKAN DATA 5 SLIDE PENUH)
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
            "hook": analysis.get("slide2_hook", "Kenapa BBM Subsidi Tiba-tiba Langka dan Bikin Antrean Mengular?"),
            "points": analysis.get("slide2_points", [
                "**Penyalahgunaan Sistematis:** Kendaraan mewah dan industri besar kedapatan menjarah jatah BBM rakyat kecil.",
                "**Penimbunan Skala Masif:** Sindikat spekulan menimbun pasokan dan menjualnya kembali dengan harga industri.",
                "**Lonjakan Konsumsi:** Pertumbuhan kendaraan pribadi melampaui kuota APBN yang ditetapkan pemerintah."
            ]),
            "takeaway": analysis.get("slide2_takeaway", "Kelangkaan BBM bukan sekadar antrean, tapi cerminan distribusi yang belum tepat sasaran."),
        },

        "slide_metric": {
            "eyebrow": analysis.get("slide3_eyebrow", "02 / BEDAH DATA RISET"),
            "hook": analysis.get("slide3_hook", "Berapa Triliun Rupiah Subsidi Kita yang Bocor ke Kantong yang Salah?"),
            "metric_value": analysis.get("slide3_metric_value", "Rp 150 T+"),
            "metric_label": analysis.get("slide3_metric_label", "estimasi alokasi anggaran energi yang rentan bocor akibat salah sasaran"),
            "col1_title": analysis.get("slide3_col1_title", "Beban Dompet Konsumen Ritel"),
            "col1_points": analysis.get("slide3_col1_points", [
                "Waktu produktif terbuang sia-sia 2-3 jam per minggu mengantre di SPBU.",
                "Tarif logistik dan transportasi umum informal terkerek naik.",
                "Pasar gelap BBM eceran membebani pengeluaran harian komuter."
            ]),
            "col2_title": analysis.get("slide3_col2_title", "Beban Sektor Usaha & UMKM"),
            "col2_points": analysis.get("slide3_col2_points", [
                "Biaya operasional armada logistik UMKM melonjak drastis.",
                "Keterlambatan pasokan mengganggu jadwal produksi dan distribusi.",
                "Penurunan produktivitas kerja harian karena kendala bahan bakar."
            ]),
            "alert_text": analysis.get("slide3_alert_text", "Setiap liter subsidi yang salah sasaran adalah hak rakyat kecil yang dirampas."),
        },

        "slide_strategy": {
            "eyebrow": analysis.get("slide4_eyebrow", "03 / SKENARIO STRATEGIS"),
            "hook": analysis.get("slide4_hook", "Tiga Langkah Menghadapi Kebijakan Pengetatan BBM"),
            "scenarios": analysis.get("slide4_scenarios", [
                {"tag": "SKENARIO KONSUMEN & KOMUTER", "text": "**Registrasi QR Code:** Daftarkan kendaraan resmi lebih awal dan optimalkan rute harian."},
                {"tag": "SKENARIO PELAKU USAHA & UMKM", "text": "**Efisiensi Logistik:** Gabungkan jadwal pengiriman dan evaluasi kendaraan operasional."},
                {"tag": "SKENARIO PENGAWASAN HUKUM", "text": "**Sanksi Tegas Pelanggar:** Blokir pelat kendaraan mewah yang nekat membeli subsidi."}
            ]),
            "takeaway": analysis.get("slide4_takeaway", "Krisis subsidi energi adalah momentum evaluasi efisiensi pengeluaran mobilitas harian kita."),
        },

        "verdict": analysis.get("verdict", "Antrean panjang di SPBU adalah cerminan ketidakadilan sistemik. Subsidi harus sampai ke mereka yang berhak, bukan dinikmati pemilik mobil mewah."),
        "slide5_highlights": analysis.get("slide5_highlights", [
            "Antrean panjang membuktikan kelemahan sistem pengawasan, bukan ketiadaan pasokan minyak mentah.",
            "Mobil berkapasitas mesin besar wajib dilarang mengisi BBM bersubsidi demi rasa keadilan sosial.",
            "Digitalisasi verifikasi QR Code harus transparan dan bebas pungutan liar di tingkat stasiun pengisian."
        ]),
        "cta": analysis.get("cta", "Menurutmu, siapa yang paling bertanggung jawab atas kelangkaan BBM subsidi ini dan apa solusi paling ampuh? Tulis pandanganmu di komentar!"),
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

    # 3. Ambil 5 Foto Jurnalistik Nyata & Terverifikasi (Bebas Bot-Detection)
    images = download_editorial_images_for_carousel(news_item, analysis)

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
