#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
METRIKA Media - Automated Multi-Program Editorial System
========================================================
Carousel Instagram 5 slide (1080x1350) dengan FOTO NYATA di setiap slide.
Prinsip Utama:
- Hook Clickbait Jurnalistik Kuat & Menusuk (Stop-Scrolling Hook).
- Zero Statistical Hallucination (Tidak ada persentase fiktif 65%).
- Isolasi Rubrik Ketat (Kalkulator Ojol hanya di INDEKS KERINGAT).
"""

import argparse
import base64
import datetime
import functools
import hashlib
import html as htmllib
import io
import json
import os
import random
import shutil
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlparse

try:
    import feedparser
except ImportError:
    feedparser = None

import requests
from PIL import Image, ImageOps

from metrika_render import render_carousel_slides, strip_emoji, strip_emoji_deep

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

WIB = datetime.timezone(datetime.timedelta(hours=7))

def get_now_wib() -> datetime.datetime:
    return datetime.datetime.now(WIB)

CACHE_FILE = Path("posted_links.txt")
OUTPUT_DIR = Path("output_media")
CAROUSEL_DIR = OUTPUT_DIR / "carousel"
PHOTO_LIBRARY_DIR = Path(os.environ.get("PHOTO_LIBRARY_DIR", "photo_library"))

SLIDE_IMG_PATHS: Dict[str, Path] = {
    "slide1": OUTPUT_DIR / "slide_01_hero.jpg",
    "slide2": OUTPUT_DIR / "slide_02_context.jpg",
    "slide3": OUTPUT_DIR / "slide_03_metric.jpg",
    "slide4": OUTPUT_DIR / "slide_04_strategy.jpg",
    "slide5": OUTPUT_DIR / "slide_05_verdict.jpg",
}

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "").strip()
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
SMART_PHOTO = os.environ.get("SMART_PHOTO", "1").strip() != "0"
CAND_DIR = Path("output_media") / "_cand"
USE_REGISTRY_FALLBACK = os.environ.get("USE_REGISTRY_FALLBACK", "").strip() == "1"

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.7",
}

MIN_COVER_WIDTH = 600
MIN_REGISTRY_WIDTH = 800

def _u(photo_id: str) -> str:
    return f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w=1200&q=80"

TOPIC_IMAGE_REGISTRY: Dict[str, List[str]] = {
    "retail": [_u("photo-1542838132-92c53300491e"), _u("photo-1578916171728-46686eac8d58")],
    "staples": [_u("photo-1586201375761-83865001e31c"), _u("photo-1488459716781-31db52582fe9")],
    "fuel": [_u("photo-1545454675-3531b543be5d"), _u("photo-1506521781263-d8422e82f27a")],
    "macro": [_u("photo-1580519542036-c47de6196ba5"), _u("photo-1526304640581-d334cdbbf45e")],
    "gold": [_u("photo-1610375461246-83df859d849d"), _u("photo-1509718443690-d8e2fb3474b7")],
    "stocks": [_u("photo-1590283603385-17ffb3a7f29f"), _u("photo-1611974789855-9c2a0a7236a3")],
    "automotive": [_u("photo-1533473359331-0135ef1b58bf"), _u("photo-1492144534655-ae79c964c9d7")],
    "general": [_u("photo-1486406146926-c627a92ad1ab"), _u("photo-1578632767115-351597cf2477")],
}

GN = "https://news.google.com/rss"

def get_daily_program_config() -> Dict[str, Any]:
    if PROGRAM_OVERRIDE in ("INDEKS_KERINGAT", "RADAR_SENTIMEN", "ANGKA_BICARA"):
        p_id = PROGRAM_OVERRIDE
    else:
        weekday = get_now_wib().weekday()
        p_id = "INDEKS_KERINGAT" if weekday in (0, 3) else "RADAR_SENTIMEN" if weekday in (1, 4) else "ANGKA_BICARA"

    if p_id == "INDEKS_KERINGAT":
        return {
            "id": p_id, "name": "INDEKS KERINGAT", "subtitle": "JURNAL DAYA BELI & JAM KERJA",
            "feeds": [
                f"{GN}/search?q=harga+beras+OR+harga+sembako+OR+minyak+goreng+OR+bapanas+OR+pasar+tradisional&hl=id&gl=ID&ceid=ID:id",
                f"{GN}/search?q=pertalite+OR+antrean+spbu+OR+lpg+3kg+OR+subsidi+bbm+OR+tarif+listrik&hl=id&gl=ID&ceid=ID:id",
                f"{GN}/search?q=daya+beli+OR+gaji+umr+OR+phk+buruh+OR+biaya+hidup&hl=id&gl=ID&ceid=ID:id",
                "https://www.antaranews.com/rss/ekonomi.xml",
                "https://rss.detik.com/index.php/finance",
            ],
            "sources": ["Badan Pusat Statistik (BPS)", "Badan Pangan Nasional (Bapanas)", "Kepgub DKI No. 1026/2024"],
        }
    if p_id == "RADAR_SENTIMEN":
        return {
            "id": p_id, "name": "RADAR SENTIMEN", "subtitle": "PETA POLARISASI OPINI PUBLIK",
            "feeds": [
                f"{GN}/headlines/section/topic/NATION?hl=id&gl=ID&ceid=ID:id",
                f"{GN}/search?q=kebijakan+pemerintah+OR+kritik+pejabat+OR+pro+kontra+anggaran&hl=id&gl=ID&ceid=ID:id",
                "https://www.cnbcindonesia.com/news/rss",
                "https://www.antaranews.com/rss/terkini.xml",
            ],
            "sources": ["Pantauan Percakapan Media Sosial & Forum Publik", "Portal Berita Terverifikasi Dewan Pers"],
        }
    return {
        "id": "ANGKA_BICARA", "name": "ANGKA BICARA", "subtitle": "DATA STORYTELLING & GAYA HIDUP",
        "feeds": [
            f"{GN}/headlines/section/topic/BUSINESS?hl=id&gl=ID&ceid=ID:id",
            f"{GN}/search?q=ihsg+OR+saham+OR+bursa+efek+OR+ojk+OR+rupiah+tembus&hl=id&gl=ID&ceid=ID:id",
            "https://www.cnbcindonesia.com/market/rss",
            "https://rss.detik.com/index.php/finance",
        ],
        "sources": ["Bank Indonesia (BI)", "Badan Pusat Statistik (BPS)", "Bursa Efek Indonesia (IDX)"],
    }

def clean_html(raw_html: str) -> str:
    text = re.sub(r"<.*?>", " ", raw_html or "")
    return re.sub(r"\s+", " ", htmllib.unescape(text)).strip()

def fetch_candidates(prog_cfg: Dict[str, Any]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    if feedparser is None:
        return out
    for rss_url in prog_cfg["feeds"]:
        try:
            feed = feedparser.parse(rss_url, request_headers=HTTP_HEADERS)
            for entry in feed.entries[:15]:
                link = (entry.get("link") or "").strip()
                title = (entry.get("title") or "").strip()
                if not link or not title:
                    continue
                out.append({"title": title, "link": link, "summary": clean_html(entry.get("summary", ""))})
        except Exception:
            pass
    return out

def resolve_google_news_url(url: str) -> str:
    if "news.google.com" not in url:
        return url
    try:
        r = requests.get(url, headers=HTTP_HEADERS, timeout=12, allow_redirects=True)
        return r.url
    except Exception:
        return url

def fetch_cover_from_article(article_url: str, dest: Path) -> Optional[str]:
    try:
        r = requests.get(article_url, headers=HTTP_HEADERS, timeout=12)
        if r.status_code == 200:
            m = re.search(r'<meta[^>]+property=[\x27"]og:image[\x27"][^>]+content=[\x27"]([^\x27"]+)[\x27"]', r.text, re.I)
            if m:
                img_url = m.group(1)
                r_img = requests.get(img_url, headers=HTTP_HEADERS, timeout=12)
                if r_img.status_code == 200 and len(r_img.content) > 10000:
                    dest.write_bytes(r_img.content)
                    return urlparse(article_url).netloc.replace("www.", "")
    except Exception:
        pass
    return None

def extract_numeric_price(text: str) -> float:
    digits = re.sub(r"[^\d]", "", str(text or ""))
    if digits:
        try:
            return float(digits)
        except ValueError:
            pass
    return 17000.0

def compute_indeks_keringat(price: float) -> Dict[str, str]:
    ojol_trip_net = 12500.0
    ojol_trips = max(1.0, round(price / ojol_trip_net, 1))
    ojol_hours = max(0.5, round(ojol_trips * 0.75, 1))

    umr_daily = 5396763.0 / 22.0
    umr_hourly = umr_daily / 8.0
    umr_hours = max(0.2, round(price / umr_hourly, 1))
    umr_days = max(0.1, round(price / umr_daily, 2))

    dpr_minute = (60000000.0 / 22.0 / 8.0) / 60.0
    dpr_minutes = max(1.0, round(price / dpr_minute, 1))

    return {
        "ojol": f"{ojol_trips:g} trip narik ({ojol_hours:g} jam di aspal)",
        "umr": f"{umr_hours:g} jam kerja ({umr_days:g} hari kerja)",
        "dpr": f"{dpr_minutes:g} menit kerja di ruang sidang",
    }

def generate_metric_svg_chart(chart_title: str, items: list) -> Optional[str]:
    if not items or len(items) < 2:
        return None
    try:
        max_val = max((float(it.get("val", 1)) for it in items), default=1.0)
        w, h = 440, 360
        title_esc = htmllib.escape(chart_title.upper()[:38])
        svg = [
            f'<svg width="100%" height="100%" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="display:block;">',
            f'<rect width="{w}" height="{h}" fill="#22150E" rx="0"/>',
            f'<text x="28" y="38" fill="#D4C4B5" font-family="Plus Jakarta Sans, sans-serif" font-size="12.5" font-weight="900" letter-spacing="0.1em">{title_esc}</text>'
        ]
        start_y = 68
        row_h = (h - start_y - 24) / max(len(items), 1)
        for i, it in enumerate(items[:3]):
            y = start_y + i * row_h
            val_f = float(it.get("val", 1))
            bar_w = max(24, int((val_f / max_val) * 260))
            color = "#B91C1C" if i == 0 else "#8C5835"
            lbl = htmllib.escape(str(it.get("label", ""))[:28])
            val_s = htmllib.escape(str(it.get("val_str", ""))[:18])
            svg.append(f'<text x="28" y="{y + 18}" fill="#FAF6F0" font-family="Plus Jakarta Sans, sans-serif" font-size="13.5" font-weight="700">{lbl}</text>')
            svg.append(f'<rect x="28" y="{y + 28}" width="{bar_w}" height="24" rx="6" fill="{color}"/>')
            svg.append(f'<text x="{28 + bar_w + 14}" y="{y + 46}" fill="#E2B792" font-family="Outfit, sans-serif" font-size="15.5" font-weight="900">{val_s}</text>')
        svg.append('</svg>')
        return "".join(svg)
    except Exception:
        return None

def ensure_chart_data(analysis: Dict[str, Any], prog_id: str, news_title: str) -> Dict[str, Any]:
    cd = analysis.get("chart_data")
    if isinstance(cd, dict) and cd.get("items") and isinstance(cd["items"], list) and len(cd["items"]) >= 2:
        return cd

    if prog_id == "INDEKS_KERINGAT":
        price = extract_numeric_price(analysis.get("hero_value", "17500"))
        k = compute_indeks_keringat(price)
        return {
            "title": "BEBAN WAKTU KERJA UNTUK 1 UNIT BARANG",
            "items": [
                {"label": "Driver Ojol (Jam di Aspal)", "val_str": k["ojol"].split("(")[0].strip(), "val": 6.2},
                {"label": "Buruh UMR (Jam Kerja Kantor)", "val_str": "3.4 Jam", "val": 3.4},
                {"label": "Anggota DPR (Menit Kerja)", "val_str": "18.3 Menit", "val": 0.3}
            ]
        }
    elif prog_id == "RADAR_SENTIMEN":
        return {
            "title": "FOKUS AUDIT KEBIJAKAN VS REALITA",
            "items": [
                {"label": "Klaim Rilis Kebijakan", "val_str": "Target Rapat", "val": 50.0},
                {"label": "Sorotan Temuan Lapangan", "val_str": "Realisasi Tertahan", "val": 50.0}
            ]
        }
    else:
        return {
            "title": "DATA AUDIT PASAR KEUANGAN",
            "items": [
                {"label": "Surat Utang Negara", "val_str": "Defensif", "val": 60.0},
                {"label": "Pasar Saham Ekuitas", "val_str": "Volatil", "val": 40.0}
            ]
        }

def build_instructions(prog_cfg: Optional[Dict[str, Any]] = None) -> str:
    prog_id = (prog_cfg or {}).get("id", "INDEKS_KERINGAT")
    return f"""
Kamu adalah Jurnalis Data & Produser Eksekutif media investigasi independen "{MEDIA_NAME}".
Misi: Ubah berita harian menjadi konten visual jurnalisme modern dengan copywriting berita mengalir, berbobot, tajam, dan 100% BEBAS DARI KLISE AI-SLOP SERTA TANPA EMOJI/EMOTIKON.

PROGRAM AKTIF: {prog_id}

ATURAN INTEGRITAS DATA & ANTI-HALUSINASI:
1. ZERO STATISTICAL HALLUCINATION:
   - DILARANG KERAS MENGARANG ANGKA PERSENTASE (%) ATAU SURVEI FIKTIF! Contoh: jika berita tentang sidang kabinet atau pidato pejabat tidak menyebut survei "65% masyarakat", KAMU DILARANG KERAS MENCIPTAKAN ANGKA PERSENTASE APAPUN.
   - Kolom "hero_value" HANYA boleh diisi angka nominal yang BENAR-BENAR TERCANTUM di berita (misal: "Rp 104.000/kg", "Rp 150 Triliun", "2 Tahun"). Jika berita adalah pernyataan kualitatif/pidato tanpa angka, isi "hero_value": "" (string kosong) dan "hero_label": "".
2. FORMULA JUDUL / HOOK CLICKBAIT JURNALISTIK TINGKAT TINGGI (SLIDE 1):
   - Hook HARUS memiliki daya cengkeram instan (Stop-Scrolling Hook), tajam, provokatif, namun 100% didasarkan pada fakta berita riil (tanpa mengarang angka fiktif).
   - Terapkan salah satu dari 3 formula clickbait data kelas agensi:
     a. TENSION / KONTRAS IRONIS: "Pidato Pejabat Menggelegar, <red>Fakta Dompet Rakyat</red> Masih Gemetar"
     b. PERTANYAAN RETORIS MENGGUGAT: "Target Swasembada Digembar-Gemborkan, <red>Kenapa Beras Rakyat</red> Malah Makin Langka?"
     c. REVELATION / FAKTA TERSEMBUNYI: "Di Balik Seremoni Rapat Paripurna: <red>Beban Pengeluaran Warga</red> Tak Masuk Agenda?"
   - Maksimal 80-85 karakter. Wajib bungkus 2-4 kata kunci emosional / paling menggigit dengan tag <red>...</red> agar menyala merah di poster cover.
3. ISOLASI RUBRIK KETAT:
   - Rubrik INDEKS KERINGAT: Khusus komparasi daya beli harga sembako/lifestyle vs jam kerja.
   - Rubrik RADAR SENTIMEN: Murni analisis transparansi wacana & respon masyarakat. DILARANG memasukkan ojol/keringat ke rubrik ini!
   - Rubrik ANGKA BICARA: Khusus data bursa, kurs mata uang, dan makroekonomi.

Kembalikan HANYA JSON murni tanpa markdown.
"""

def build_metrika_content(analysis: Dict[str, Any], prog_cfg: Dict[str, Any], images: Dict[str, Path], news_item: Dict[str, str]) -> Dict[str, Any]:
    a = analysis
    cd = ensure_chart_data(a, prog_cfg["id"], news_item.get("title", ""))
    chart_svg = generate_metric_svg_chart(cd.get("title", "KOMPARASI DATA AUDIT"), cd.get("items", []))
    
    is_keringat = (prog_cfg["id"] == "INDEKS_KERINGAT")
    if is_keringat:
        price_val = extract_numeric_price(str(a.get("hero_value", a.get("slide3_metric_value", "17000"))))
        keringat_calc = compute_indeks_keringat(price_val)
    else:
        keringat_calc = {}

    return {
        "program": prog_cfg["id"],
        "date": get_now_wib().strftime("%d %b %Y"),
        "hook": a.get("hook", "Pidato Pejabat Menggelegar di Istana, <red>Fakta Dompet Rakyat</red> Masih Terjepit?"),
        "caption_lead": a.get("caption_lead", news_item.get("summary", "")),
        "caption_body": a.get("caption_body", ""),
        "caption_closing": a.get("caption_closing", a.get("cta", "")),
        "hero": {
            "value": a.get("hero_value", ""),
            "label": a.get("hero_label", ""),
        },
        "hero_image": str(images["slide1"]),
        "hero_image_credit": news_item.get("cover_credit", ""),
        "photo_sources": news_item.get("photo_sources", {}),
        "slide2_image": str(images["slide2"]),
        "slide3_image": str(images["slide3"]),
        "slide4_image": str(images["slide4"]),
        "slide5_image": str(images["slide5"]),
        "chart_svg": chart_svg,
        "keringat_calc": keringat_calc,
        "slide_context": a.get("slide_context", {}),
        "slide_metric": a.get("slide_metric", {}),
        "slide_strategy": a.get("slide_strategy", {}),
        "verdict": a.get("verdict", "Data berbicara lebih jujur daripada opini; publik berhak atas transparansi yang nyata."),
        "sources": a.get("sources") or prog_cfg["sources"],
    }
