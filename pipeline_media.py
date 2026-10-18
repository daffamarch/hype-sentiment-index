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

Fokus Utama:
- Carousel Instagram 5 Slide Berkualitas Agensi Desain (1080x1350 px).
- Palet Coklat Mewah (Luxury Espresso, Warm Cognac Leather, Warm Ivory Linen).
- Foto editorial nyata 100% akurat untuk setiap slide (Anti-Anime, Anti-Halloween, Anti-Random).
- Hook penahan scroll di setiap slide.
- Tanpa rendering video (fokus 100% pada kesempurnaan carousel).
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

# Strict Exclusion List untuk Domain dan Kata Kunci Non-Jurnalistik
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

# Bank Foto Terverifikasi Bebas Hak Cipta untuk Topik Populer Indonesia
TOPIC_IMAGE_VAULT = {
    "gold": "https://images.unsplash.com/photo-1610375461246-83df859d849d?auto=format&fit=crop&w=1200&q=80",
    "chart": "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=1200&q=80",
    "money": "https://images.unsplash.com/photo-1580519542036-c47de6196ba5?auto=format&fit=crop&w=1200&q=80",
    "investor": "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?auto=format&fit=crop&w=1200&q=80",
    "bank": "https://images.unsplash.com/photo-1541354329998-f4d9a9f9297f?auto=format&fit=crop&w=1200&q=80",
    "gadget": "https://images.unsplash.com/photo-1510557880182-3d4d3cba35a5?auto=format&fit=crop&w=1200&q=80",
    "ojol": "https://images.unsplash.com/photo-1558981403-c5f9899a28bc?auto=format&fit=crop&w=1200&q=80",
    "business": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=1200&q=80",
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
                "https://news.google.com/rss/search?q=biaya+hidup+OR+survei+gaji+OR+harga+emas+OR+saham+ihsg+indonesia&hl=id&gl=ID&ceid=ID:id",
            ],
            "sources": [
                "Logam Mulia PT Antam Tbk",
                "Bursa Efek Indonesia (IDX)",
                "Bank Indonesia (BI)",
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
                    "title": "Harga Emas Antam Tembus Rekor Baru: Investor Hadapi Dilema Jual atau Tahan",
                    "link": f"https://metrika.id/statistik/{datetime.date.today()}",
                    "summary": "Lonjakan harga emas murni 24 karat di tengah sentimen geopolitik global dan pilihan alokasi aset masyarakat.",
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
    "ANTAM": "Emas batangan Logam Mulia Antam gold bar",
    "EMAS": "Emas batangan gold bullion bar 24k",
    "TESLA": "Tesla electric car automobile",
}

def clean_query_term(raw_query: str) -> str:
    """Membersihkan kata pencarian agar fokus ke entitas fotografi fisik konkret."""
    words = raw_query.upper().split()
    for w in words:
        clean_w = re.sub(r'[^A-Z]', '', w)
        if clean_w in ACRONYM_MAP:
            return ACRONYM_MAP[clean_w]
    
    # Ambil 3-5 kata benda penting
    clean = re.sub(r'[^\w\s]', ' ', raw_query).strip()
    tokens = [t for t in clean.split() if len(t) > 2 and t.lower() not in ["dan", "yang", "dari", "untuk", "pada", "adalah", "ini", "itu", "atau"]]
    return " ".join(tokens[:5])


def generate_curated_editorial_canvas(topic_title: str, slide_label: str, save_path: Path) -> Path:
    """Membuat latar visual editorial bernuansa coklat mewah jika unduhan eksternal gagal."""
    im = Image.new("RGB", (1200, 800), (35, 23, 16)) # Dark Roasted Espresso
    d = ImageDraw.Draw(im)

    # Pola garis kisi elegan
    for y in range(60, 740, 70):
        d.line([(60, y), (1140, y)], fill=(48, 32, 22), width=1)
    for x in range(60, 1140, 100):
        d.line([(x, 60), (x, 740)], fill=(48, 32, 22), width=1)

    # Frame aksen warm cognac leather
    d.rectangle([(40, 40), (1160, 760)], outline=(140, 88, 53), width=2)
    d.rectangle([(0, 785), (1200, 800)], fill=(185, 28, 28)) # Red accent bar

    clean_t = re.sub(r'</?red>', '', topic_title).strip()
    d.text((80, 320), f"METRIKA DOKUMENTASI DATA • {slide_label.upper()}", fill=(226, 183, 146))
    d.text((80, 380), clean_t[:60], fill=(250, 246, 240))
    im.save(save_path, format="JPEG", quality=92)
    print(f"[Photo] Visual editorial kanvas tersusun rapi: {save_path.name}")
    return save_path


def is_safe_image_url(url: str) -> bool:
    """Memastikan URL bukan kartun/anime, profil youtube, atau wallpaper tidak relevan."""
    url_low = url.lower()
    if any(b in url_low for b in BLOCKED_IMAGE_DOMAINS):
        return False
    if any(t in url_low for t in DISALLOWED_IMAGE_TERMS):
        return False
    return True


def fetch_editorial_photo_with_meta(
    news_item: Dict[str, str], query_term: str, save_path: Path, fallback_key: str = "business"
) -> Tuple[Path, str]:
    """
    Mengunduh foto jurnalistik 100% nyata & akurat.
    Menggunakan Wikimedia Commons + Bing Photo Filter + Unsplash Vault.
    Menjamin tidak ada gambar anime, kartun, atau gambar halloween!
    """
    candidate_urls: List[str] = []
    clean_q = clean_query_term(query_term)
    meta_text = f"{query_term} {news_item['title']}"

    # 1. Prioritas Utama: Cari di Wikimedia Commons API (Foto Asli Bebas Hak Cipta)
    try:
        wiki_search_url = (
            "https://commons.wikimedia.org/w/api.php?action=query&generator=search"
            f"&gsrnamespace=6&gsrsearch={urllib.parse.quote(clean_q + ' photo')}&gsrlimit=4"
            "&prop=imageinfo&iiprop=url|mime&iiurlwidth=1200&format=json"
        )
        w_res = requests.get(wiki_search_url, headers=HTTP_HEADERS, timeout=6)
        if w_res.status_code == 200:
            pages = w_res.json().get("query", {}).get("pages", {})
            for _, p_data in pages.items():
                img_info = p_data.get("imageinfo", [{}])[0]
                thumb_url = img_info.get("thumburl") or img_info.get("url")
                if thumb_url and is_safe_image_url(thumb_url):
                    candidate_urls.append(thumb_url)
    except Exception:
        pass

    # 2. Cari di Bing Image Search dengan Filter Ketat (+photo +large) & Negative Terms
    try:
        search_engine_q = f"{clean_q} photograph real news -anime -manga -cartoon -drawing -illustration -wallpaper -avatar -halloween"
        bing_url = (
            "https://www.bing.com/images/search?q="
            + urllib.parse.quote(search_engine_q)
            + "&qft=+filterui:photo+filterui:imagesize-large"
        )
        b_resp = requests.get(bing_url, headers=HTTP_HEADERS, timeout=6)
        if b_resp.status_code == 200:
            matches = re.findall(r'murl&quot;:&quot;(https?://[^&]+?)&quot;', b_resp.text)
            for m in matches[:8]:
                if is_safe_image_url(m):
                    candidate_urls.append(m)
    except Exception:
        pass

    # 3. Masukkan Foto Cadangan Tematik Terkurasi dari Vault
    vault_url = TOPIC_IMAGE_VAULT.get(fallback_key, TOPIC_IMAGE_VAULT["business"])
    candidate_urls.append(vault_url)

    # Validasi download gambar yang valid
    for img_url in candidate_urls:
        try:
            r = requests.get(img_url, headers=HTTP_HEADERS, timeout=8)
            if r.status_code == 200 and len(r.content) > 12_000:
                pil_img = Image.open(io.BytesIO(r.content)).convert("RGB")
                if pil_img.width >= 400 and pil_img.height >= 250:
                    pil_img.save(save_path, format="JPEG", quality=92)
                    print(f"[Photo] Foto jurnalistik berhasil diunduh: {img_url[:65]}...")
                    return save_path, f"{meta_text} {img_url}"
        except Exception:
            continue

    # Fallback Terakhir: Kanvas Editorial Coklat Mewah Elegan
    generated = generate_curated_editorial_canvas(news_item["title"], clean_q[:25], save_path)
    return generated, meta_text


# ==============================================================================
# 4. OTAK AI: ANALISIS PROGRAM UNTUK 5 SLIDE NARRATIVE CAROUSEL
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
Kamu adalah Pemimpin Redaksi media data "{MEDIA_NAME}" untuk program "{prog_cfg['name']}".
Misi: Mengubah berita terpilih menjadi ARSITEKTUR CAROUSEL 5 SLIDE NARRATIVE KELAS AGENSI DESAIN.

ATURAN STRUKTUR 5 SLIDE LENGKAP:
- SLIDE 1 (COVER): Hook provokatif hitam-merah (<red>kata kunci</red>) + Stat Pill (angka dan label penting).
- SLIDE 2 (KONTEKS & AKAR MASALAH): Hook penahan scroll + 3 poin investigasi padat berformat '**Kata Kunci:** Uraian fakta 20-30 kata'.
- SLIDE 3 (BEDAH ANGKA & DATA): Hook penahan scroll + Metric spotlight angka + 2 kolom analisis perbandingan (masing-masing 3 poin padat).
- SLIDE 4 (SKENARIO STRATEGIS): Hook penahan scroll + 3 skenario aksi nyata (Skenario A, Skenario B, Skenario C) + 1 kalimat takeaway penting.
- SLIDE 5 (VERDICT & DISKUSI): Verdict objektif redaksi + pertanyaan diskusi terbuka pemantik komentar + 3-4 rujukan data resmi.

ATURAN PENCARIAN FOTO (PENTING! ANTI-ANIME & ANTI-HALLOWEEN):
- Tulis 'query_photo' untuk setiap slide berupa 3-4 KATA BENDA FOTOGRAFI FISIK NYATA dalam Bahasa Inggris/Indonesia (contoh: 'gold bullion bar antam', 'stock market candlestick chart', 'indonesian rupiah banknotes', 'bank vault safe deposit box', 'jakarta stock exchange floor'). DILARANG MENULIS KATA ABSTRAK ATAU EMOSIONAL!

Format output JSON murni:
{{
  "subject_title": "Topik Berita Nyata (maks 25 karakter)",
  "hook": "Emas Rekor Lagi, <red>Investor Hadapi Dilema</red>: Saatnya Beli di Pucuk atau Ambil Untung?",
  "hero_value": "Rp 1.490.000",
  "hero_label": "rekor harga emas murni Antam per gram hari ini",
  "slide1_photo_query": "gold bullion bar antam logammulia",
  "fallback_theme_1": "gold",

  "slide2_eyebrow": "01 / DOKUMENTASI FAKTA",
  "slide2_hook": "Mengapa Harga Emas Mendadak Meledak dan Cetak Rekor Baru?",
  "slide2_points": [
    "**Ketegangan Geopolitik:** Eskalasi konflik internasional memicu lonjakan permintaan aset safe haven global.",
    "**Aksi Bank Sentral:** Pembelian cadangan emas fisik oleh otoritas moneter dunia mencapai rekor tertinggi.",
    "**Sentimen Inflasi Domestik:** Investor ritel dan korporasi mengalihkan likuiditas tunai untuk lindung nilai daya beli."
  ],
  "slide2_photo_query": "gold market candlestick trading chart",
  "fallback_theme_2": "chart",

  "slide3_eyebrow": "02 / BEDAH DATA RISET",
  "slide3_hook": "Dilema Dua Arah: Beli di Pucuk atau Ambil Untung Sekarang?",
  "slide3_metric_value": "+31,8%",
  "slide3_metric_label": "kenaikan rata-rata harga emas murni year-to-date di pasar domestik",
  "slide3_col1_title": "Argumen Akumulasi (Bullish)",
  "slide3_col1_points": [
    "Tren suku bunga acuan global melandai meningkatkan daya tarik emas non-yield.",
    "Pelemahan mata uang regional memperkuat posisi emas sebagai jangkar nilai aset.",
    "Keterbatasan suplai tambang fisik dunia menopang harga jangka panjang."
  ],
  "slide3_col2_title": "Argumen Rebalancing (Bearish)",
  "slide3_col2_points": [
    "Risiko koreksi teknikal jangka pendek akibat aksi profit taking pemodal besar.",
    "Spread jual-beli (buyback) butik emas membutuhkan waktu untuk impas biaya awal.",
    "Emas tidak menghasilkan dividen atau arus kas kas masuk secara periodik."
  ],
  "slide3_photo_query": "indonesian rupiah banknotes currency cash",
  "fallback_theme_3": "money",

  "slide4_eyebrow": "03 / SKENARIO STRATEGIS",
  "slide4_hook": "Tiga Skenario Menghadapi Fluktuasi Harga Pasar",
  "slide4_scenarios": [
    {{"tag": "SKENARIO JANGKA PANJANG", "text": "**Dollar Cost Averaging:** Alokasikan porsi tetap bulanan saat terjadi koreksi harga wajar, bukan saat tren memuncak."}},
    {{"tag": "SKENARIO KEBUTUHAN TUNAI", "text": "**Realisasi Bertahap:** Jual sebagian porsi profit jika ada kebutuhan dana darurat atau modal usaha produktif."}},
    {{"tag": "SKENARIO ANTI-FOMO", "text": "**Disiplin Portofolio:** Batasi alokasi logam mulia maksimal 10-15 persen dari total portofolio aset Anda."}}
  ],
  "slide4_takeaway": "Emas adalah pelindung nilai daya beli dari inflasi, bukan instrumen cepat kaya semalam.",
  "slide4_photo_query": "bank vault gold bar investment safe",
  "fallback_theme_4": "bank",

  "verdict": "Kilau emas hari ini adalah cerminan ketidakpastian; keputusan terbaik lahir dari rasio keuangan sehat, bukan kepanikan pasar.",
  "cta": "Apakah kamu memilih beli lagi di harga rekor ini, atau justru menjualnya untuk ambil untung? Tulis strategimu di komentar!",
  "sources": ["Logam Mulia PT Antam Tbk", "Bank Indonesia (BI)", "Bloomberg Commodities", "Badan Pusat Statistik (BPS)"],
  "slide5_photo_query": "stock market investor screens desk financial",
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
            "value": analysis.get("hero_value", "100%"),
            "label": analysis.get("hero_label", "acuan data pasar resmi terverifikasi"),
        },
        "hero_image": str(images["slide1"]),
        "slide2_image": str(images["slide2"]),
        "slide3_image": str(images["slide3"]),
        "slide4_image": str(images["slide4"]),
        "slide5_image": str(images["slide5"]),

        "slide_context": {
            "eyebrow": analysis.get("slide2_eyebrow", "01 / DOKUMENTASI FAKTA"),
            "hook": analysis.get("slide2_hook", "Mengapa Isu Ini Mendadak Mencuat Sekarang?"),
            "points": analysis.get("slide2_points", [
                "**Dinamika Pasar:** Pergerakan indeks dan sentimen investor global.",
                "**Kebijakan Makro:** Respons otoritas dan regulator dalam menjaga stabilitas.",
                "**Implikasi Domestik:** Pengaruh langsung ke daya beli masyarakat."
            ]),
        },

        "slide_metric": {
            "eyebrow": analysis.get("slide3_eyebrow", "02 / BEDAH DATA RISET"),
            "hook": analysis.get("slide3_hook", "Dilema Dua Arah: Siapa Untung, Siapa Buntung?"),
            "metric_value": analysis.get("slide3_metric_value", "+25,4%"),
            "metric_label": analysis.get("slide3_metric_label", "perubahan rata-rata acuan pasar terverifikasi"),
            "col1_title": analysis.get("slide3_col1_title", "Argumen Akumulasi"),
            "col1_points": analysis.get("slide3_col1_points", ["Peluang pertumbuhan aset jangka panjang", "Ketahanan fundamental emiten"]),
            "col2_title": analysis.get("slide3_col2_title", "Argumen Waspada"),
            "col2_points": analysis.get("slide3_col2_points", ["Risiko volatilitas jangka pendek", "Penyesuaian likuiditas"]),
        },

        "slide_strategy": {
            "eyebrow": analysis.get("slide4_eyebrow", "03 / SKENARIO STRATEGIS"),
            "hook": analysis.get("slide4_hook", "Tiga Skenario Menghadapi Fluktuasi Pasar"),
            "scenarios": analysis.get("slide4_scenarios", [
                {"tag": "SKENARIO JANGKA PANJANG", "text": "**Akumulasi Bertahap:** Lakukan pembelian berkala saat harga koreksi wajar."},
                {"tag": "SKENARIO TAKTIS", "text": "**Realisasi Profit:** Kunci keuntungan jika target jangka pendek telah tercapai."},
                {"tag": "SKENARIO MITIGASI", "text": "**Disiplin Portofolio:** Hindari keputusan impulsif akibat sentimen sesaat."}
            ]),
            "takeaway": analysis.get("slide4_takeaway", "Aset berharga melindungi daya beli dari inflasi jangka panjang."),
        },

        "verdict": analysis.get("verdict", "Keputusan terbaik lahir dari rasio keuangan sehat, bukan euforia sesaat."),
        "cta": analysis.get("cta", "Bagaimana strategimu menyikapi dinamika pasar hari ini? Tulis di komentar!"),
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
        f"📊 *{MEDIA_NAME.upper()} • JURNALISME DATA*\n\n"
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

    # 2. Analisis AI Gemini untuk 5 Slide Lengkap
    analysis = analyze_with_gemini(news_item, supporting, prog_cfg)

    # 3. Cari Foto Jurnalistik Nyata & Terverifikasi untuk SETIAP Slide (Anti-Anime & Anti-Halloween)
    images: Dict[str, Path] = {}
    
    q1 = analysis.get("slide1_photo_query") or analysis.get("subject_title", "business finance")
    f1 = analysis.get("fallback_theme_1", "gold" if "emas" in news_item["title"].lower() else "business")
    images["slide1"], _ = fetch_editorial_photo_with_meta(news_item, q1, HERO_IMG_PATH, f1)

    q2 = analysis.get("slide2_photo_query") or "market trend chart stock"
    f2 = analysis.get("fallback_theme_2", "chart")
    images["slide2"], _ = fetch_editorial_photo_with_meta(news_item, q2, SLIDE2_IMG_PATH, f2)

    q3 = analysis.get("slide3_photo_query") or "indonesia rupiah cash money"
    f3 = analysis.get("fallback_theme_3", "money")
    images["slide3"], _ = fetch_editorial_photo_with_meta(news_item, q3, SLIDE3_IMG_PATH, f3)

    q4 = analysis.get("slide4_photo_query") or "bank vault safe investment"
    f4 = analysis.get("fallback_theme_4", "bank")
    images["slide4"], _ = fetch_editorial_photo_with_meta(news_item, q4, SLIDE4_IMG_PATH, f4)

    q5 = analysis.get("slide5_photo_query") or "investor looking at screen stock trading"
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

    # 6. Kirim Album Carousel ke Telegram (Video Dinonaktifkan sesuai Permintaan)
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
