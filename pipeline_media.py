#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hype & Sentiment Index - Anti-AI-Slop Editorial Media Pipeline (100% Cloud)
===========================================================================
Upgrade Visual Setara Redaksi Profesional (Folkative / Bloomberg Quicktake):
1. Real News Photo Scraper: Menyedot foto asli kejadian/tokoh dari artikel berita
   (via og:image / Bing News Image fallback) — BUKAN gambar AI halusinasi.
2. Multi-Scene Dynamic Video (3 Babak Visual) + Ken Burns Effect (Zoom-In Halus):
   - Scene 1 (0-33% durasi): Breaking News Hero Photo + Live Ticker & Sentiment Score
   - Scene 2 (33-68% durasi): Interactive Market Chart + Fundamental Kronologi Card
   - Scene 3 (68-100% durasi): Netizen Sentiment Breakdown + Verdict (Buy / Hold / Sell)
3. Karaoke Word-by-Word Highlighting Subtitle: Menggunakan timestamp WordBoundary asli
   dari Edge-TTS sehingga kata yang sedang diucapkan menyala otomatis (gaya CapCut Pro).
4. Editorial Dark-Mode Carousel (1080x1350): Slide 1 memadukan foto berita asli dengan
   gradasi gelap (dark vignette) dan grafik bursa efek.
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

import edge_tts
import feedparser
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

# ==============================================================================
# 1. KONFIGURASI LINGKUNGAN & KONSTANTA GLOBAL
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

RSS_FEEDS = [
    "https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?hl=id&gl=ID&ceid=ID:id",
    "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=id&gl=ID&ceid=ID:id",
    "https://news.google.com/rss/search?q=viral+OR+trending+OR+netizen+indonesia&hl=id&gl=ID&ceid=ID:id",
]

CACHE_FILE = Path("posted_links.txt")
OUTPUT_DIR = Path("output_media")
CAROUSEL_DIR = OUTPUT_DIR / "carousel"
AUDIO_PATH = OUTPUT_DIR / "voiceover.mp3"
SUBTITLE_PATH = OUTPUT_DIR / "subtitles.vtt"
HERO_IMG_PATH = OUTPUT_DIR / "news_hero.jpg"
FINAL_VIDEO_PATH = OUTPUT_DIR / "tiktok_reels_hype_index.mp4"

TTS_VOICE = "id-ID-ArdiNeural"
TTS_RATE = "+5%"

CAROUSEL_WIDTH = 1080
CAROUSEL_HEIGHT = 1350
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920

# Palet Warna Dark-Mode Editorial (Bloomberg / Stockbit Style)
COLOR_BG = (11, 15, 25)            # #0B0F19 Deep Navy-Black
COLOR_CARD = (20, 27, 45)          # #141B2D Dark Slate Card
COLOR_CARD_ALT = (28, 38, 62)      # #1C263E Highlight Card
COLOR_BORDER = (42, 56, 86)        # #2A3856 Crisp Border
COLOR_TEXT_MAIN = (243, 244, 246)  # #F3F4F6 Pure Crisp White
COLOR_TEXT_MUTED = (156, 163, 175) # #9CA3AF Muted Metallic Gray
COLOR_BULLISH = (16, 185, 129)     # #10B981 Market Green
COLOR_BEARISH = (239, 68, 68)      # #EF4444 Market Red
COLOR_NEUTRAL = (245, 158, 11)     # #F59E0B Market Amber
COLOR_ACCENT = (56, 189, 248)      # #38BDF8 Cyber Cyan
COLOR_HIGHLIGHT = (250, 204, 21)   # #FACC15 Karaoke Active Word Yellow

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ==============================================================================
# 2. UTILITAS FONT & PEMBERSIH TEKS
# ==============================================================================
def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Memuat font TrueType dari sistem Linux/Ubuntu (GitHub Actions) atau fallback default."""
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
    """Membersihkan tag HTML dari ringkasan RSS."""
    clean_regex = re.compile("<.*?>")
    text = re.sub(clean_regex, " ", raw_html or "")
    return re.sub(r"\s+", " ", text).strip()


# ==============================================================================
# 3. MODUL NEWS INGESTION & REAL PHOTO SCRAPER (ANTI-AI-SLOP)
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


def extract_image_from_rss_entry(entry: Any) -> Optional[str]:
    """Mencari URL gambar langsung dari tag media_content atau summary RSS jika ada."""
    for attr in ("media_content", "media_thumbnail"):
        media_list = entry.get(attr, [])
        if isinstance(media_list, list):
            for item in media_list:
                url = item.get("url", "")
                if url and url.startswith("http"):
                    return url

    raw_summary = entry.get("summary", "")
    if "<img" in raw_summary:
        soup = BeautifulSoup(raw_summary, "html.parser")
        img_tag = soup.find("img")
        if img_tag and img_tag.get("src", "").startswith("http"):
            return img_tag["src"]
    return None


def fetch_latest_unposted_news() -> Tuple[Dict[str, str], List[str]]:
    posted = load_posted_links()
    candidates: List[Dict[str, str]] = []

    for rss_url in RSS_FEEDS:
        print(f"[RSS] Mengambil feed: {rss_url}")
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:15]:
            link = entry.get("link", "").strip()
            title = entry.get("title", "").strip()
            summary = clean_html(entry.get("summary", ""))
            published = entry.get("published", "")
            rss_img = extract_image_from_rss_entry(entry) or ""
            if link and title and link not in posted:
                candidates.append(
                    {
                        "title": title,
                        "link": link,
                        "summary": summary,
                        "published": published,
                        "rss_image": rss_img,
                    }
                )

    if not candidates:
        raise RuntimeError(
            "Tidak ditemukan berita baru yang belum diposting di RSS Feed hari ini."
        )

    primary_news = candidates[0]
    supporting_headlines = [item["title"] for item in candidates[1:6]]
    print(f"[RSS] Berita terpilih: {primary_news['title']}")
    return primary_news, supporting_headlines


def fetch_real_editorial_photo(
    news_item: Dict[str, str], entity_name: str, save_path: Path
) -> Optional[Image.Image]:
    """
    Mengambil foto jurnalistik asli (Real Photo) agar video tidak terlihat seperti AI Slop:
    1. Mencoba mengambil meta `og:image` / `twitter:image` dari halaman artikel berita.
    2. Jika terhalang redirect Google News, mencari thumbnail berita asli dari Bing News
       berdasarkan judul berita / nama topik.
    """
    image_urls_to_try: List[str] = []

    if news_item.get("rss_image"):
        image_urls_to_try.append(news_item["rss_image"])

    # Lapis 1: Coba scrape og:image dari URL artikel
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
                    url_candidate = meta["content"].strip()
                    # Hindari logo default Google News
                    if "lh3.googleusercontent.com/J6_coFbogxhRI9iM864NL_liGXvsQp2AupsKei7z0cNNfDvGUmWUy20nuUhkREQyrpY4bEeIBuc" not in url_candidate:
                        image_urls_to_try.append(url_candidate)
    except Exception as exc:
        print(f"[Photo] Info: Gagal baca og:image langsung ({exc}), lanjut ke pencarian berita.")

    # Lapis 2: Cari foto jurnalistik asli lewat halaman Bing News Search (tanpa API Key)
    search_query = f"{entity_name} {news_item['title'][:45]}"
    bing_url = (
        "https://www.bing.com/images/search?q="
        + urllib.parse.quote(search_query)
        + "&qft=+filterui:imagesize-large"
    )
    try:
        b_resp = requests.get(bing_url, headers=HTTP_HEADERS, timeout=12)
        if b_resp.status_code == 200:
            matches = re.findall(r'murl&quot;:&quot;(https?://[^&]+?)&quot;', b_resp.text)
            for m in matches[:5]:
                if m not in image_urls_to_try:
                    image_urls_to_try.append(m)
    except Exception as exc:
        print(f"[Photo] Info: Pencarian gambar alternatif dilewati ({exc}).")

    # Unduh kandidat gambar pertama yang valid dan beresolusi layak
    for img_url in image_urls_to_try:
        try:
            img_resp = requests.get(img_url, headers=HTTP_HEADERS, timeout=12)
            if img_resp.status_code == 200 and len(img_resp.content) > 15_000:
                pil_img = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
                if pil_img.width >= 300 and pil_img.height >= 200:
                    pil_img.save(save_path, format="JPEG", quality=92)
                    print(
                        f"[Photo] Berhasil mengunduh foto berita asli ({pil_img.width}x{pil_img.height}) dari: {img_url[:65]}..."
                    )
                    return pil_img
        except Exception:
            continue

    print("[Photo] Menggunakan latar belakang editorial gradien (foto berita tidak tersedia).")
    return None


def crop_and_zoom_photo(
    photo: Optional[Image.Image],
    target_w: int,
    target_h: int,
    zoom_factor: float = 1.0,
    darken: float = 0.55,
) -> Image.Image:
    """
    Memotong foto berita asli agar pas ke rasio kotak (center-crop), menerapkan efek
    Ken Burns (zoom-in halus dari frame ke frame), serta menambahkan dark vignette
    agar teks & grafik di atasnya terbaca sangat tajam.
    """
    if photo is None:
        fallback = Image.new("RGB", (target_w, target_h), color=COLOR_CARD)
        return fallback

    src_w, src_h = photo.size
    target_ratio = target_w / float(target_h)
    src_ratio = src_w / float(src_h)

    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        new_h = src_h
    else:
        new_w = src_w
        new_h = int(src_w / target_ratio)

    # Terapkan zoom_factor (>1.0 berarti crop sedikit lebih kecil lalu di-resize)
    zoom_w = max(10, int(new_w / max(zoom_factor, 1.0)))
    zoom_h = max(10, int(new_h / max(zoom_factor, 1.0)))

    left = (src_w - zoom_w) // 2
    top = (src_h - zoom_h) // 2
    cropped = photo.crop((left, top, left + zoom_w, top + zoom_h))
    resized = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)

    # Redupkan sedikit kecerahan agar teks putih/hijau kontras di atas foto
    enhancer = ImageEnhance.Brightness(resized)
    darkened = enhancer.enhance(darken)

    # Tambahkan gradasi gelap di bagian bawah foto (vignette fade ke COLOR_BG)
    gradient = Image.new("L", (1, target_h), color=0)
    for y in range(target_h):
        if y < int(target_h * 0.45):
            alpha = 0
        else:
            prog = (y - target_h * 0.45) / (target_h * 0.55)
            alpha = int(min(255, prog * 245))
        gradient.putpixel((0, y), alpha)

    alpha_mask = gradient.resize((target_w, target_h))
    bg_layer = Image.new("RGB", (target_w, target_h), color=COLOR_BG)
    blended = Image.composite(bg_layer, darkened, alpha_mask)
    return blended


# ==============================================================================
# 4. MODUL OTAK AI: AUTO-DETECT MODEL GEMINI & PROMPT EDITORIAL TAJAM
# ==============================================================================
def get_available_gemini_models() -> List[str]:
    if GEMINI_MODEL_OVERRIDE:
        clean_override = GEMINI_MODEL_OVERRIDE.replace("models/", "")
        return [clean_override] + [
            m for m in PREFERRED_GEMINI_MODELS if m != clean_override
        ]

    list_url = (
        f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    )
    discovered_models: List[str] = []

    try:
        resp = requests.get(list_url, timeout=20)
        resp.raise_for_status()
        models_payload = resp.json().get("models", [])
        for m in models_payload:
            name = m.get("name", "").replace("models/", "")
            methods = m.get("supportedGenerationMethods", [])
            if (
                "generateContent" in methods
                and name.startswith("gemini-")
                and not any(
                    excl in name
                    for excl in ("embedding", "imagen", "veo", "tts", "aqa", "vision")
                )
            ):
                discovered_models.append(name)
    except Exception as exc:
        print(f"[Gemini] Info query model ({exc}), memakai daftar prioritas bawaan.")
        return list(PREFERRED_GEMINI_MODELS)

    if not discovered_models:
        return list(PREFERRED_GEMINI_MODELS)

    ordered: List[str] = []
    for pref in PREFERRED_GEMINI_MODELS:
        if pref in discovered_models and pref not in ordered:
            ordered.append(pref)
    for m in sorted(discovered_models, reverse=True):
        if "flash" in m and m not in ordered:
            ordered.append(m)
    for m in sorted(discovered_models, reverse=True):
        if m not in ordered:
            ordered.append(m)

    print(f"[Gemini] Urutan kandidat model: {', '.join(ordered[:5])}")
    return ordered


def analyze_news_with_gemini(
    primary_news: Dict[str, str], supporting_headlines: List[str]
) -> Dict[str, Any]:
    """
    Memanggil Google Gemini API dengan instruksi khusus Anti-AI-Slop:
    dilarang memakai pembuka klise AI ("Halo guys", "Tahukah kamu"), wajib langsung
    masuk dengan Hook tajam ala jurnalis pasar modal & kultur pop (Bloomberg / Folkative).
    """
    if not GEMINI_API_KEY:
        raise EnvironmentError(
            "Environment variable GEMINI_API_KEY belum diatur! Pastikan sudah dipasang di GitHub Secrets."
        )

    supporting_str = "\n".join(f"- {hl}" for hl in supporting_headlines)
    prompt = f"""
Kamu adalah Redaktur Eksekutif dari media pop-culture & tren anak muda Indonesia bernama "HYPE & SENTIMENT INDEX" (perpaduan gaya Folkative dan terminal Bloomberg/IDX).
Konsep utama: Setiap tokoh, brand, atau kejadian viral diperlakukan seperti emiten saham di lantai bursa.

Berita utama hari ini:
- Judul: {primary_news['title']}
- Ringkasan: {primary_news['summary']}
- Waktu Rilis: {primary_news['published']}

Headline tren pendamping di pasar hari ini:
{supporting_str}

ATURAN PENULISAN ANTI-AI-SLOP (WAJIB DIPATUHI):
1. DILARANG KERAS memulai voiceover dengan kalimat klise robot/AI seperti "Halo semuanya", "Balik lagi di", "Tahukah kamu", atau "Hari ini kita akan membahas".
2. Kalimat pertama "voiceover_script" WAJIB langsung berupa HOOK tajam di detik pertama (contoh: "Saham sentimen $TIMN langsung terbang 18 persen pagi ini gara-gara..." atau "Panic selling melanda lantai bursa netizen setelah...").
3. Gunakan bahasa Indonesia jurnalis muda Jakarta yang cerdas, mengalir, lugas, dan enak didengar saat dibacakan cepat (sekitar 75-95 kata, tanpa singkatan aneh atau simbol dolar di dalam voiceover_script agar pelafalan TTS mulus).

Kembalikan HANYA objek JSON murni (tanpa pembungkus markdown ```json) dengan struktur kunci persis berikut:
{{
  "ticker_symbol": "Kode saham 4 huruf kapital diawali $, contoh: $DRMA, $TIMN, $MUSK",
  "entity_name": "Nama subjek/tokoh/brand utama (maks 26 karakter)",
  "sentiment_score": 78,
  "price_change_pct": "+14.5%",
  "market_status": "BULLISH",
  "verdict_action": "STRONG BUY",
  "chart_points": [42, 48, 45, 55, 62, 70, 78],
  "scene_highlights": [
    "Fakta Pemicu: Ringkasan 1 kalimat padat tentang pemicu utama kehebohan ini (maks 95 karakter).",
    "Sentimen Netizen: Ringkasan 1 kalimat tajam soal kubu pro vs kontra di medsos (maks 95 karakter).",
    "Proyeksi Hype: Prediksi apakah tren ini bakal lanjut naik atau segera koreksi (maks 95 karakter)."
  ],
  "voiceover_script": "Naskah voiceover 75-95 kata dengan Hook detik pertama yang kuat, tanpa simbol $ atau tanda baca aneh.",
  "telegram_caption": "Caption Instagram & TikTok yang engaging lengkap dengan ringkasan skor indeks dan 5 hashtag.",
  "carousel_slides": [
    {{
      "slide_number": 1,
      "tag": "BREAKING MARKET • HYPE INDEX",
      "headline": "Judul cover slide 1 yang tajam ala headline Folkative x Bloomberg (maks 52 karakter)",
      "body": "Subjudul padat yang menjelaskan kenapa emiten topik ini bergerak liar hari ini (maks 135 karakter).",
      "footer_metric": "VOLUME PERBINCANGAN: EKSTREM"
    }},
    {{
      "slide_number": 2,
      "tag": "KRONOLOGI & FUNDAMENTAL",
      "headline": "Apa Pemicu Utamanya?",
      "body": "Penjelasan fakta inti berita secara jernih, tanpa basa-basi (maks 210 karakter).",
      "footer_metric": "KATALIS UTAMA HARI INI"
    }},
    {{
      "slide_number": 3,
      "tag": "PETA SENTIMEN NETIZEN",
      "headline": "Respons Pasar & Komentar Publik",
      "body": "Bedah argumen kubu pendukung vs pengkritik yang menggerakkan skor sentimen (maks 210 karakter).",
      "footer_metric": "INDEKS SENTIMEN PUBLIK"
    }},
    {{
      "slide_number": 4,
      "tag": "EFEK DOMINO INDUSTRI",
      "headline": "Dampaknya ke Tren & Brand",
      "body": "Bagaimana insiden atau tren ini memengaruhi reputasi tokoh/brand ke depannya (maks 210 karakter).",
      "footer_metric": "VOLATILITAS SEKTOR"
    }},
    {{
      "slide_number": 5,
      "tag": "RADAR EMITEN TREN LAIN",
      "headline": "Top Movers Lain di Bursa Hari Ini",
      "body": "Rangkuman singkat 2-3 berita tren pendamping hari ini beserta arah sentimennya (maks 210 karakter).",
      "footer_metric": " pantauan indeks harian"
    }},
    {{
      "slide_number": 6,
      "tag": "KEPUTUSAN REDAKSI",
      "headline": "Verdict Hype Besok: Buy, Hold, atau Sell?",
      "body": "Rekomendasi akhir apakah topik ini layak terus diikuti (Buy/Hold) atau sudah jenuh (Sell) (maks 195 karakter).",
      "footer_metric": "BAGIKAN KE TEMAN DISKUSIMU"
    }}
  ]
}}
""".strip()

    candidate_models = get_available_gemini_models()
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.55,
            "responseMimeType": "application/json",
        },
    }

    last_error: Optional[Exception] = None
    for model_name in candidate_models:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:generateContent?key={GEMINI_API_KEY}"
        )
        try:
            print(f"[Gemini] Mencoba analisis dengan model: {model_name}...")
            response = requests.post(url, json=payload, timeout=60)
            if response.status_code != 200:
                continue

            data = response.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            cleaned_json = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text.strip())
            parsed: Dict[str, Any] = json.loads(cleaned_json)
            parsed["_model_used"] = model_name
            print(
                f"[Gemini] Sukses ({model_name}): {parsed.get('ticker_symbol')} | "
                f"{parsed.get('market_status')} ({parsed.get('sentiment_score')}%)"
            )
            return parsed
        except Exception as exc:
            last_error = exc

    raise RuntimeError(f"Seluruh kandidat model Gemini gagal: {last_error}")


# ==============================================================================
# 5. MODUL VOICEOVER & KARAOKE WORD TIMESTAMPS (EDGE-TTS)
# ==============================================================================
async def _generate_voiceover_and_word_timings(
    script_text: str, audio_out: Path, subtitle_out: Path
) -> List[Dict[str, Any]]:
    """
    Membuat audio .mp3 sekaligus menangkap waktu mulai & selesai setiap kata
    (`WordBoundary`) untuk dirender menjadi Subtitle Karaoke Kinetik ala CapCut Pro.
    """
    communicate = edge_tts.Communicate(
        text=script_text, voice=TTS_VOICE, rate=TTS_RATE
    )
    word_timings: List[Dict[str, Any]] = []

    with audio_out.open("wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # offset dan duration dari edge-tts dalam satuan 100-nanoseconds (1e-7 detik)
                start_sec = float(chunk.get("offset", 0)) / 10_000_000.0
                dur_sec = float(chunk.get("duration", 0)) / 10_000_000.0
                word_text = str(chunk.get("text", "")).strip()
                if word_text:
                    word_timings.append(
                        {
                            "word": word_text,
                            "start": start_sec,
                            "end": start_sec + max(dur_sec, 0.12),
                        }
                    )

    subtitle_out.write_text(
        json.dumps(word_timings, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return word_timings


def generate_voiceover(
    script_text: str, audio_out: Path, subtitle_out: Path
) -> List[Dict[str, Any]]:
    print(f"[Edge-TTS] Merekam voiceover + word timing dengan suara {TTS_VOICE}...")
    timings = asyncio.run(
        _generate_voiceover_and_word_timings(script_text, audio_out, subtitle_out)
    )
    print(
        f"[Edge-TTS] Audio selesai ({len(timings)} penanda kata terekam untuk subtitle karaoke)."
    )
    return timings


# ==============================================================================
# 6. KOMPONEN GRAFIS BURSA EFEK & RENDER CAROUSEL INSTAGRAM (4:5)
# ==============================================================================
def get_status_color(market_status: str) -> Tuple[int, int, int]:
    status_upper = (market_status or "").upper()
    if "BULL" in status_upper or "NAIK" in status_upper or "BUY" in status_upper:
        return COLOR_BULLISH
    if "BEAR" in status_upper or "TURUN" in status_upper or "SELL" in status_upper:
        return COLOR_BEARISH
    return COLOR_NEUTRAL


def draw_stock_chart(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    points: List[int],
    line_color: Tuple[int, int, int],
) -> None:
    x0, y0, x1, y1 = box
    width = x1 - x0
    height = y1 - y0

    draw.rounded_rectangle(box, radius=20, fill=COLOR_CARD, outline=COLOR_BORDER, width=2)

    for i in range(1, 4):
        gy = y0 + int((height / 4) * i)
        draw.line([(x0 + 24, gy), (x1 - 24, gy)], fill=COLOR_BORDER, width=1)

    if not points or len(points) < 2:
        points = [45, 50, 48, 60, 65, 72, 78]

    min_val = min(points)
    max_val = max(points)
    span = max(max_val - min_val, 10)

    pad_x = 45
    pad_y = 38
    usable_w = width - (pad_x * 2)
    usable_h = height - (pad_y * 2)

    coords: List[Tuple[int, int]] = []
    for idx, val in enumerate(points):
        px = x0 + pad_x + int((idx / (len(points) - 1)) * usable_w)
        norm = (val - min_val) / span
        py = y1 - pad_y - int(norm * usable_h)
        coords.append((px, py))

    draw.line(coords, fill=line_color, width=6, joint="curve")

    for idx, (px, py) in enumerate(coords):
        radius = 9 if idx == len(coords) - 1 else 5
        draw.ellipse(
            (px - radius, py - radius, px + radius, py + radius),
            fill=line_color,
            outline=COLOR_TEXT_MAIN,
            width=2,
        )


def render_carousel_slides(
    analysis: Dict[str, Any], hero_photo: Optional[Image.Image], out_dir: Path
) -> List[Path]:
    """
    Merender 6 slide Carousel Instagram (1080x1350 px).
    Slide 1 memadukan Foto Jurnalistik Asli + Dark Vignette + Grafik Indeks Sentimen.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    slides_data = analysis.get("carousel_slides", [])
    total_slides = len(slides_data)

    ticker = analysis.get("ticker_symbol", "$TREN")
    entity_name = analysis.get("entity_name", "Topik Viral Hari Ini")
    score = analysis.get("sentiment_score", 75)
    pct = analysis.get("price_change_pct", "+12.0%")
    status = analysis.get("market_status", "BULLISH").upper()
    chart_points = analysis.get("chart_points", [40, 45, 50, 58, 63, 70, int(score)])

    status_color = get_status_color(status)

    font_ticker = load_font(32, bold=True)
    font_badge = load_font(25, bold=True)
    font_tag = load_font(23, bold=True)
    font_headline = load_font(50, bold=True)
    font_body = load_font(34, bold=False)
    font_metric = load_font(25, bold=True)
    font_footer = load_font(23, bold=False)

    generated_files: List[Path] = []
    today_str = datetime.datetime.now().strftime("%d %b %Y").upper()

    for idx, slide in enumerate(slides_data, start=1):
        img = Image.new("RGB", (CAROUSEL_WIDTH, CAROUSEL_HEIGHT), color=COLOR_BG)

        # Jika Slide 1 dan foto berita asli tersedia, pasang di setengah atas kanvas
        if idx == 1 and hero_photo is not None:
            banner = crop_and_zoom_photo(
                hero_photo, CAROUSEL_WIDTH, 620, zoom_factor=1.02, darken=0.62
            )
            img.paste(banner, (0, 0))

        draw = ImageDraw.Draw(img)

        # Header Bar Terminal
        header_box = (60, 50, CAROUSEL_WIDTH - 60, 145)
        draw.rounded_rectangle(
            header_box, radius=18, fill=COLOR_CARD, outline=COLOR_BORDER, width=2
        )
        draw.text(
            (88, 80),
            f"{ticker} • {entity_name[:20].upper()}",
            font=font_ticker,
            fill=COLOR_TEXT_MAIN,
        )

        badge_text = f"{status} {pct} ({score}%)"
        badge_w = 340
        badge_box = (CAROUSEL_WIDTH - 85 - badge_w, 68, CAROUSEL_WIDTH - 85, 127)
        draw.rounded_rectangle(badge_box, radius=12, fill=status_color)
        draw.text(
            (CAROUSEL_WIDTH - 85 - badge_w + 20, 83),
            badge_text,
            font=font_badge,
            fill=COLOR_BG,
        )

        curr_y = 430 if (idx == 1 and hero_photo is not None) else 195

        slide_tag = slide.get("tag", f"ANALISIS PASAR #{idx}").upper()
        draw.text((70, curr_y), slide_tag, font=font_tag, fill=COLOR_ACCENT)
        curr_y += 42

        headline_text = slide.get("headline", "Update Pergerakan Hype Hari Ini")
        wrapped_headline = textwrap.wrap(headline_text, width=27)[:3]
        for line in wrapped_headline:
            draw.text((70, curr_y), line, font=font_headline, fill=COLOR_TEXT_MAIN)
            curr_y += 62

        curr_y += 20

        if idx == 1:
            chart_h = 260 if hero_photo is not None else 340
            chart_box = (70, curr_y, CAROUSEL_WIDTH - 70, curr_y + chart_h)
            draw_stock_chart(draw, chart_box, chart_points, status_color)
            curr_y += chart_h + 25

        body_text = slide.get("body", "")
        wrapped_body = textwrap.wrap(body_text, width=42)[:6]
        card_height = max(200, len(wrapped_body) * 48 + 65)
        body_bottom = min(curr_y + card_height, 1150)
        body_box = (70, curr_y, CAROUSEL_WIDTH - 70, body_bottom)
        draw.rounded_rectangle(
            body_box, radius=20, fill=COLOR_CARD, outline=COLOR_BORDER, width=2
        )
        draw.rounded_rectangle(
            (70, curr_y, 84, body_bottom), radius=6, fill=status_color
        )

        text_y = curr_y + 32
        for line in wrapped_body:
            if text_y + 40 < body_bottom:
                draw.text((112, text_y), line, font=font_body, fill=COLOR_TEXT_MAIN)
                text_y += 46

        footer_metric = slide.get("footer_metric", "HYPE & SENTIMENT INDEX").upper()
        draw.text((70, 1185), f"⚡ {footer_metric}", font=font_metric, fill=status_color)

        draw.line([(70, 1240), (CAROUSEL_WIDTH - 70, 1240)], fill=COLOR_BORDER, width=2)
        draw.text(
            (70, 1265),
            f"HYPE & SENTIMENT INDEX • {today_str}",
            font=font_footer,
            fill=COLOR_TEXT_MUTED,
        )
        draw.text(
            (CAROUSEL_WIDTH - 220, 1265),
            f"SLIDE {idx} / {total_slides}  →",
            font=font_footer,
            fill=COLOR_TEXT_MAIN,
        )

        slide_path = out_dir / f"slide_{idx:02d}.png"
        img.save(slide_path, format="PNG", optimize=True)
        generated_files.append(slide_path)

    print(f"[Pillow] Berhasil merender {len(generated_files)} slide carousel editorial.")
    return generated_files


# ==============================================================================
# 7. MODUL RENDER VIDEO MULTI-SCENE + KEN BURNS + KARAOKE SUBTITLE (ANTI-SLOP)
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
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    try:
        return max(float(result.stdout.strip()), 5.0)
    except ValueError:
        return 30.0


def draw_karaoke_subtitle_box(
    draw: ImageDraw.ImageDraw,
    word_timings: List[Dict[str, Any]],
     fallback_words: List[str],
    current_sec: float,
    total_duration: float,
    status_color: Tuple[int, int, int],
    font_sub: ImageFont.FreeTypeFont,
) -> None:
    """
    Menggambar kotak subtitle di mana kelompok 6 kata ditampilkan sekaligus, dan
    kata yang sedang diucapkan tepat pada detik `current_sec` menyala warna KUNING EMAS
    (`COLOR_HIGHLIGHT`) seperti editor video profesional.
    """
    sub_box = (65, 1410, VIDEO_WIDTH - 65, 1690)
    draw.rounded_rectangle(
        sub_box, radius=24, fill=(15, 21, 36), outline=status_color, width=3
    )

    group_size = 6
    if word_timings:
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
    else:
        total_w = max(len(fallback_words), 1)
        active_idx = min(
            int((current_sec / max(total_duration, 1.0)) * total_w), total_w - 1
        )
        group_start = (active_idx // group_size) * group_size
        group_slice_str = fallback_words[group_start : group_start + group_size]
        tokens = [
            (w.upper(), (group_start + idx) == active_idx)
            for idx, w in enumerate(group_slice_str)
        ]

    # Tata kata menjadi maksimal 2 baris di dalam kotak subtitle
    lines: List[List[Tuple[str, bool]]] = [[]]
    curr_char_len = 0
    for word_str, is_active in tokens:
        if curr_char_len + len(word_str) > 20 and len(lines) < 2:
            lines.append([])
            curr_char_len = 0
        lines[-1].append((word_str, is_active))
        curr_char_len += len(word_str) + 1

    start_y = 1465 if len(lines) == 2 else 1510
    for line_tokens in lines:
        full_line_str = " ".join(t[0] for t in line_tokens)
        line_bbox = draw.textbbox((0, 0), full_line_str, font=font_sub)
        line_w = line_bbox[2] - line_bbox[0]
        curr_x = (VIDEO_WIDTH - line_w) // 2

        for word_str, is_active in line_tokens:
            word_color = COLOR_HIGHLIGHT if is_active else COLOR_TEXT_MAIN
            draw.text((curr_x, start_y), word_str, font=font_sub, fill=word_color)
            w_bbox = draw.textbbox((0, 0), word_str + " ", font=font_sub)
            curr_x += w_bbox[2] - w_bbox[0]

        start_y += 68


def render_vertical_video(
    analysis: Dict[str, Any],
    hero_photo: Optional[Image.Image],
    word_timings: List[Dict[str, Any]],
    audio_path: Path,
    video_out: Path,
) -> Path:
    """
    Merender video vertikal 9:16 (1080x1920) dengan 3 Babak Visual (Multi-Scene)
    dan foto berita asli beranimasi Ken Burns Zoom agar bebas dari kesan AI Slop.
    """
    frames_dir = OUTPUT_DIR / "video_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    duration = get_audio_duration(audio_path)
    fps = 12
    total_frames = int(math.ceil(duration * fps))

    ticker = analysis.get("ticker_symbol", "$TREN")
    entity_name = analysis.get("entity_name", "Topik Viral Indonesia")
    score = int(analysis.get("sentiment_score", 78))
    pct = analysis.get("price_change_pct", "+14.5%")
    status = analysis.get("market_status", "BULLISH").upper()
    verdict = analysis.get("verdict_action", "HOLD / WATCH").upper()
    raw_points = analysis.get("chart_points", [40, 46, 52, 58, 64, 71, score])
    script_text = analysis.get("voiceover_script", "")
    scene_highlights = analysis.get(
        "scene_highlights",
        [
            "Fakta Utama: Pergerakan topik ini memicu lonjakan diskusi publik.",
            "Sentimen Netizen: Mayoritas warganet memberikan respons kuat di media sosial.",
            "Proyeksi Indeks: Volatilitas diperkirakan masih tinggi hingga besok.",
        ],
    )

    status_color = get_status_color(status)
    fallback_words = script_text.split() or ["PANTAU", "INDEKS", "HARI", "INI"]

    font_header = load_font(36, bold=True)
    font_scene_tag = load_font(26, bold=True)
    font_title = load_font(48, bold=True)
    font_score = load_font(82, bold=True)
    font_card_body = load_font(34, bold=False)
    font_sub = load_font(44, bold=True)
    font_small = load_font(26, bold=False)

    interp_points: List[float] = []
    steps_per_seg = max(total_frames // max(len(raw_points) - 1, 1), 1)
    for i in range(len(raw_points) - 1):
        start_v = float(raw_points[i])
        end_v = float(raw_points[i + 1])
        for s in range(steps_per_seg):
            t = s / float(steps_per_seg)
            interp_points.append(start_v + (end_v - start_v) * t)
    while len(interp_points) < total_frames:
        interp_points.append(float(raw_points[-1]))

    headline = (
        analysis.get("carousel_slides", [{}])[0].get(
            "headline", f"Pergerakan Sentimen {entity_name}"
        )
    )
    wrapped_title = textwrap.wrap(headline, width=25)[:3]

    print(
        f"[Video] Merender {total_frames} frame Multi-Scene ({duration:.1f} dtk @ {fps} fps)..."
    )

    for f_idx in range(total_frames):
        current_sec = f_idx / float(fps)
        progress = f_idx / float(max(total_frames - 1, 1))

        # Tentukan babak visual (Scene 1, 2, atau 3)
        if progress < 0.34:
            scene_num = 1
            scene_label = "BABAK 1/3 • BREAKING MARKET FLASH"
        elif progress < 0.68:
            scene_num = 2
            scene_label = "BABAK 2/3 • GRAFIK & KRONOLOGI INTI"
        else:
            scene_num = 3
            scene_label = "BABAK 3/3 • REAKSI NETIZEN & VERDICT"

        img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), color=COLOR_BG)

        # Bagian Atas (Y: 0 - 840): Foto Berita Asli dengan Efek Ken Burns Zoom-In Halus
        zoom_factor = 1.0 + (progress * 0.16)
        darken_level = 0.68 if scene_num == 1 else 0.42
        top_photo_banner = crop_and_zoom_photo(
            hero_photo, VIDEO_WIDTH, 840, zoom_factor=zoom_factor, darken=darken_level
        )
        img.paste(top_photo_banner, (0, 0))

        draw = ImageDraw.Draw(img)

        # 1. Top Ticker Bar (Transparan Gelap di Atas Foto Berita)
        draw.rounded_rectangle(
            (60, 75, VIDEO_WIDTH - 60, 180),
            radius=18,
            fill=COLOR_CARD,
            outline=COLOR_BORDER,
            width=2,
        )
        draw.text(
            (90, 108),
            f"IDX-HYPE • {ticker}",
            font=font_header,
            fill=COLOR_ACCENT,
        )
        draw.rounded_rectangle(
            (VIDEO_WIDTH - 345, 95, VIDEO_WIDTH - 85, 160),
            radius=12,
            fill=status_color,
        )
        draw.text(
            (VIDEO_WIDTH - 322, 108),
            f"{status} {pct}",
            font=font_header,
            fill=COLOR_BG,
        )

        # 2. Indikator Babak (Scene Pill) & Headline di Atas Vignette Foto
        draw.rounded_rectangle(
            (65, 210, 560, 262), radius=10, fill=COLOR_CARD_ALT, outline=COLOR_ACCENT, width=1
        )
        draw.text((85, 222), scene_label, font=font_scene_tag, fill=COLOR_ACCENT)

        ty = 285
        for line in wrapped_title:
            draw.text((65, ty), line, font=font_title, fill=COLOR_TEXT_MAIN)
            ty += 60

        # 3. Konten Dinamis Berdasarkan Babak (Area Tengah Y: 520 - 1370)
        current_val = int(round(interp_points[f_idx]))

        if scene_num == 1:
            # SCENE 1: Fokus ke Foto Kejadian + Kartu Skor Sentimen Raksasa + Fakta Pemicu
            score_card = (65, 680, VIDEO_WIDTH - 65, 950)
            draw.rounded_rectangle(
                score_card, radius=24, fill=COLOR_CARD, outline=status_color, width=3
            )
            draw.text(
                (105, 715),
                f"EMITEN TREN: {entity_name.upper()}",
                font=font_scene_tag,
                fill=COLOR_TEXT_MUTED,
            )
            draw.text(
                (105, 765),
                f"{current_val}%",
                font=font_score,
                fill=status_color,
            )
            draw.text(
                (390, 790),
                f"Perubahan: {pct}\nStatus: {status}",
                font=font_header,
                fill=COLOR_TEXT_MAIN,
            )

            # Kartu Highlight Babak 1
            hl_box = (65, 990, VIDEO_WIDTH - 65, 1360)
            draw.rounded_rectangle(
                hl_box, radius=22, fill=COLOR_CARD, outline=COLOR_BORDER, width=2
            )
            draw.text(
                (105, 1030),
                "📌 PEMICU PERGERAKAN PASAR HARI INI",
                font=font_scene_tag,
                fill=COLOR_HIGHLIGHT,
            )
            hl_lines = textwrap.wrap(scene_highlights[0], width=38)[:4]
            hy = 1090
            for hline in hl_lines:
                draw.text((105, hy), hline, font=font_card_body, fill=COLOR_TEXT_MAIN)
                hy += 50

        elif scene_num == 2:
            # SCENE 2: Fokus ke Grafik Bursa Efek Interaktif + Analisis Sentimen Netizen
            visible_slice = interp_points[: max(2, f_idx + 1)]
            step = max(1, len(visible_slice) // 12)
            sampled = [int(v) for v in visible_slice[::step]]
            if sampled[-1] != int(visible_slice[-1]):
                sampled.append(int(visible_slice[-1]))

            chart_box = (65, 540, VIDEO_WIDTH - 65, 1020)
            draw_stock_chart(draw, chart_box, sampled, status_color)
            draw.text(
                (100, 565),
                f"LIVE CHART {ticker} • SKOR SAAT INI: {current_val}%",
                font=font_scene_tag,
                fill=COLOR_TEXT_MAIN,
            )

            hl_box = (65, 1055, VIDEO_WIDTH - 65, 1365)
            draw.rounded_rectangle(
                hl_box, radius=22, fill=COLOR_CARD, outline=COLOR_BORDER, width=2
            )
            draw.text(
                (105, 1090),
                "💬 PETA SENTIMEN & REAKSI NETIZEN",
                font=font_scene_tag,
                fill=COLOR_ACCENT,
            )
            hl2_text = scene_highlights[1] if len(scene_highlights) > 1 else scene_highlights[0]
            hl_lines = textwrap.wrap(hl2_text, width=38)[:4]
            hy = 1145
            for hline in hl_lines:
                draw.text((105, hy), hline, font=font_card_body, fill=COLOR_TEXT_MAIN)
                hy += 48

        else:
            # SCENE 3: Fokus ke Kartu Verdict (Buy / Hold / Sell) + Proyeksi Besok
            verdict_box = (65, 560, VIDEO_WIDTH - 65, 920)
            draw.rounded_rectangle(
                verdict_box, radius=24, fill=COLOR_CARD_ALT, outline=status_color, width=4
            )
            draw.text(
                (105, 600),
                "KEPUTUSAN REDAKSI HYPE INDEX:",
                font=font_scene_tag,
                fill=COLOR_TEXT_MUTED,
            )
            draw.text(
                (105, 655),
                verdict,
                font=font_score,
                fill=COLOR_HIGHLIGHT,
            )
            draw.text(
                (105, 785),
                f"Skor Penutupan: {score}% ({status} {pct})",
                font=font_header,
                fill=status_color,
            )

            hl_box = (65, 960, VIDEO_WIDTH - 65, 1365)
            draw.rounded_rectangle(
                hl_box, radius=22, fill=COLOR_CARD, outline=COLOR_BORDER, width=2
            )
            draw.text(
                (105, 1000),
                "🔮 PROYEKSI TREN & KESIMPULAN PASAR",
                font=font_scene_tag,
                fill=COLOR_BULLISH,
            )
            hl3_text = scene_highlights[2] if len(scene_highlights) > 2 else scene_highlights[-1]
            hl_lines = textwrap.wrap(hl3_text, width=38)[:4]
            hy = 1060
            for hline in hl_lines:
                draw.text((105, hy), hline, font=font_card_body, fill=COLOR_TEXT_MAIN)
                hy += 50

        # 4. Karaoke Subtitle Box (Kata Aktif Menyala Kuning Emas)
        draw_karaoke_subtitle_box(
            draw=draw,
            word_timings=word_timings,
            fallback_words=fallback_words,
            current_sec=current_sec,
            total_duration=duration,
            status_color=status_color,
            font_sub=font_sub,
        )

        # 5. Progress Bar Durasi Video & Footer
        bar_bg = (65, 1735, VIDEO_WIDTH - 65, 1751)
        bar_fg = (65, 1735, 65 + int((VIDEO_WIDTH - 130) * progress), 1751)
        draw.rounded_rectangle(bar_bg, radius=8, fill=COLOR_CARD)
        draw.rounded_rectangle(bar_fg, radius=8, fill=status_color)

        draw.text(
            (65, 1775),
            "HYPE & SENTIMENT INDEX • REAL NEWS & DATA TERMINAL",
            font=font_small,
            fill=COLOR_TEXT_MUTED,
        )

        frame_file = frames_dir / f"frame_{f_idx:04d}.png"
        img.save(frame_file, format="PNG")

    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(fps),
        "-i",
        str(frames_dir / "frame_%04d.png"),
        "-i",
        str(audio_path),
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=110:sample_rate=44100:duration={duration}",
        "-filter_complex",
        "[2:a]volume=0.025,lowpass=f=200[bg];[1:a][bg]amix=inputs=2:duration=first:dropout_transition=2[aout]",
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

    print("[FFmpeg] Merender file MP4 akhir...")
    subprocess.run(ffmpeg_cmd, check=True)
    print(f"[FFmpeg] Video selesai dirender: {video_out}")
    return video_out


# ==============================================================================
# 8. MODUL DISTRIBUSI OTOMATIS KE BOT TELEGRAM PRIBADI
# ==============================================================================
def send_outputs_to_telegram(
    video_path: Path,
    carousel_paths: List[Path],
    analysis: Dict[str, Any],
    news_item: Dict[str, str],
) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(
            "[Telegram] TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID belum diset. "
            "Melewati pengiriman ke Telegram."
        )
        return

    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    ticker = analysis.get("ticker_symbol", "$TREN")
    status = analysis.get("market_status", "BULLISH")
    score = analysis.get("sentiment_score", 75)
    pct = analysis.get("price_change_pct", "+10%")
    verdict = analysis.get("verdict_action", "HOLD")
    model_used = analysis.get("_model_used", "gemini-auto")
    caption_body = analysis.get("telegram_caption", "")

    header_msg = (
        f"📊 *HYPE & SENTIMENT INDEX HARI INI*\n"
        f"Emiten Tren: `{ticker}` — *{analysis.get('entity_name', '')}*\n"
        f"Status Pasar: *{status}* ({pct} | Skor: {score}% | Verdict: *{verdict}*)\n"
        f"Model AI: `{model_used}`\n"
        f"Sumber Berita: {news_item.get('title', '')}\n"
        f"Link: {news_item.get('link', '')}\n\n"
        f"📝 *Caption Siap Copy-Paste:*\n{caption_body}"
    )

    print("[Telegram] Mengirim video vertikal (.mp4) ke Telegram...")
    with video_path.open("rb") as vf:
        resp_vid = requests.post(
            f"{base_url}/sendVideo",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": header_msg[:1024],
                "parse_mode": "Markdown",
            },
            files={"video": vf},
            timeout=120,
        )
        resp_vid.raise_for_status()

    print("[Telegram] Mengirim album Carousel Instagram ke Telegram...")
    media_group = []
    files_payload = {}
    for idx, img_path in enumerate(carousel_paths[:10]):
        attach_key = f"slide_{idx}"
        files_payload[attach_key] = img_path.open("rb")
        media_item: Dict[str, Any] = {
            "type": "photo",
            "media": f"attach://{attach_key}",
        }
        if idx == 0:
            media_item["caption"] = (
                f"🖼 Carousel Instagram (4:5 Editorial Dark Mode) — {ticker} ({len(carousel_paths)} Slide)"
            )
        media_group.append(media_item)

    try:
        resp_album = requests.post(
            f"{base_url}/sendMediaGroup",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "media": json.dumps(media_group),
            },
            files=files_payload,
            timeout=120,
        )
        resp_album.raise_for_status()
    finally:
        for f_obj in files_payload.values():
            f_obj.close()

    print("[Telegram] Seluruh paket konten harian berhasil dikirim ke Telegram!")


# ==============================================================================
# 9. ORKESTRATOR UTAMA (MAIN PIPELINE)
# ==============================================================================
def main() -> None:
    print("=" * 72)
    print("🚀 MEMULAI PIPELINE HYPE & SENTIMENT INDEX (ANTI-AI-SLOP EDITION)")
    print("=" * 72)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CAROUSEL_DIR.mkdir(parents=True, exist_ok=True)

    # Tahap 1: Ambil berita terbaru yang belum pernah diposting
    primary_news, supporting_headlines = fetch_latest_unposted_news()

    # Tahap 2: Analisis sentimen & buat naskah tajam dengan Auto-Detect Model Gemini
    analysis = analyze_news_with_gemini(primary_news, supporting_headlines)

    analysis_json_path = OUTPUT_DIR / "latest_analysis.json"
    analysis_json_path.write_text(
        json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Tahap 3: Unduh foto berita jurnalistik asli (og:image / Bing News fallback)
    hero_photo = fetch_real_editorial_photo(
        primary_news, analysis.get("entity_name", ""), HERO_IMG_PATH
    )

    # Tahap 4: Buat audio voiceover + ekstraksi timestamp kata untuk Karaoke Subtitle
    voice_script = analysis.get(
        "voiceover_script",
        f"Pergerakan indeks sentimen hari ini dibuka oleh {primary_news['title']}.",
    )
    word_timings = generate_voiceover(voice_script, AUDIO_PATH, SUBTITLE_PATH)

    # Tahap 5: Render 6 slide Carousel Instagram Dark Mode (dengan Foto Asli di Slide 1)
    carousel_files = render_carousel_slides(analysis, hero_photo, CAROUSEL_DIR)

    # Tahap 6: Render Video Vertikal 9:16 Multi-Scene (Foto Ken Burns + Grafik + Karaoke Sub)
    video_file = render_vertical_video(
        analysis, hero_photo, word_timings, AUDIO_PATH, FINAL_VIDEO_PATH
    )

    # Tahap 7: Kirim paket video & gambar ke Bot Telegram Pribadi
    send_outputs_to_telegram(video_file, carousel_files, analysis, primary_news)

    # Tahap 8: Catat link berita ke posted_links.txt agar tidak duplikat besok
    save_posted_link(primary_news["link"])
    print(f"[Cache] Link berita disimpan ke {CACHE_FILE} untuk mencegah duplikasi.")
    print("✅ PIPELINE SELESAI DENGAN SUKSES!")


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"❌ [ERROR] Pipeline berhenti karena kendala: {err}", file=sys.stderr)
        sys.exit(1)
