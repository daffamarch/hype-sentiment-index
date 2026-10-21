#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
METRIKA Media - Automated Multi-Program Editorial System
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

SLIDE_IMG_PATHS: Dict[str, Path] = {
    "slide1": OUTPUT_DIR / "slide_01_hero.jpg",
    "slide2": OUTPUT_DIR / "slide_02_context.jpg",
    "slide3": OUTPUT_DIR / "slide_03_metric.jpg",
    "slide4": OUTPUT_DIR / "slide_04_strategy.jpg",
    "slide5": OUTPUT_DIR / "slide_05_verdict.jpg",
}

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.7",
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
                f"{GN}/search?q=daya+beli+OR+gaji+umr+OR+phk+buruh+OR+alfamart+OR+indomaret+OR+biaya+hidup&hl=id&gl=ID&ceid=ID:id",
                "https://www.antaranews.com/rss/ekonomi.xml",
                "https://rss.detik.com/index.php/finance",
            ],
            "sources": ["Badan Pusat Statistik (BPS)", "Badan Pangan Nasional (Bapanas)", "Kementerian ESDM RI", "Kepgub DKI (UMP Rp 5.396.763)"],
        }
    if p_id == "RADAR_SENTIMEN":
        return {
            "id": p_id, "name": "RADAR SENTIMEN", "subtitle": "PETA POLARISASI OPINI PUBLIK",
            "feeds": [
                f"{GN}/headlines/section/topic/NATION?hl=id&gl=ID&ceid=ID:id",
                f"{GN}/search?q=kebijakan+pemerintah+OR+kritik+pejabat+OR+pro+kontra+anggaran+OR+bansos&hl=id&gl=ID&ceid=ID:id",
                "https://www.cnbcindonesia.com/news/rss",
                "https://www.antaranews.com/rss/terkini.xml",
            ],
            "sources": ["Pantauan Percakapan Media Sosial & Forum Publik", "Portal Berita Terverifikasi Dewan Pers"],
        }
    return {
        "id": "ANGKA_BICARA", "name": "ANGKA BICARA", "subtitle": "DATA STORYTELLING & GAYA HIDUP",
        "feeds": [
            f"{GN}/headlines/section/topic/BUSINESS?hl=id&gl=ID&ceid=ID:id",
            f"{GN}/search?q=ihsg+OR+saham+OR+bursa+efek+OR+ojk+OR+rupiah+tembus+OR+harga+emas&hl=id&gl=ID&ceid=ID:id",
            "https://www.cnbcindonesia.com/market/rss",
            "https://www.cnbcindonesia.com/news/rss",
            "https://rss.detik.com/index.php/finance",
        ],
        "sources": ["Bank Indonesia (BI)", "Badan Pusat Statistik (BPS)", "Bursa Efek Indonesia (IDX)"],
    }

def clean_html(raw_html: str) -> str:
    text = re.sub(r"<.*?>", " ", raw_html or "")
    return re.sub(r"\s+", " ", htmllib.unescape(text)).strip()

def load_posted_links() -> set:
    if not CACHE_FILE.exists():
        CACHE_FILE.write_text("", encoding="utf-8")
        return set()
    return {ln.strip() for ln in CACHE_FILE.read_text(encoding="utf-8").splitlines() if ln.strip()}

def save_posted_link(link: str) -> None:
    with CACHE_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{link.strip()}\n")

def fetch_candidates(prog_cfg: Dict[str, Any]) -> List[Dict[str, str]]:
    posted = load_posted_links()
    seen_titles: set = set()
    out: List[Dict[str, str]] = []
    if feedparser is None:
        print("[RSS] feedparser belum terpasang.")
    else:
        for rss_url in prog_cfg["feeds"]:
            try:
                feed = feedparser.parse(rss_url, request_headers=HTTP_HEADERS)
                for entry in feed.entries[:15]:
                    link = (entry.get("link") or "").strip()
                    title = (entry.get("title") or "").strip()
                    key = re.sub(r"\W+", "", title.lower())[:60]
                    if not link or not title or link in posted or key in seen_titles:
                        continue
                    summary_text = clean_html(entry.get("summary", ""))
                    seen_titles.add(key)
                    out.append({"title": title, "link": link, "summary": summary_text, "published": entry.get("published", "")})
            except Exception as err:
                print(f"[RSS] Feed dilewati: {err}")
    return out

def resolve_google_news_url(url: str) -> str:
    if "news.google.com" not in url:
        return url
    m = re.search(r"/articles/([^?/#]+)", url)
    if not m:
        return url
    art_id = m.group(1)
    try:
        raw = base64.urlsafe_b64decode(art_id + "=" * (-len(art_id) % 4))
        mm = re.search(rb"https?://[^\x00-\x20\"'<>\x7f-\xff]+", raw)
        if mm and b"news.google.com" not in mm.group(0):
            return mm.group(0).decode("utf-8", "ignore")
    except Exception:
        pass
    return url

META_RE = re.compile(r"<meta\s+[^>]*>", re.I)
ATTR_RE = re.compile(r'([\w:-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')')
OG_KEYS = ("og:image:secure_url", "og:image", "og:image:url", "twitter:image")

def download_image(url: str, path: Path, min_width: int = 600) -> bool:
    try:
        r = requests.get(url, headers=HTTP_HEADERS, timeout=15)
        if r.status_code != 200 or len(r.content) < 10_000:
            return False
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(r.content))).convert("RGB")
        if im.width < min_width:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        im.save(path, format="JPEG", quality=92)
        return True
    except Exception:
        return False

def fetch_cover_from_article(article_url: str, dest: Path) -> Optional[str]:
    try:
        r = requests.get(article_url, headers=HTTP_HEADERS, timeout=15, allow_redirects=True)
        final = r.url
        host = urlparse(final).netloc.lower().replace("www.", "")
        if r.status_code != 200:
            return None
        found = {}
        for tag in META_RE.findall(r.text[:400000]):
            attrs = {}
            for m in ATTR_RE.finditer(tag):
                attrs[m.group(1).lower()] = htmllib.unescape(m.group(2) if m.group(2) is not None else m.group(3))
            key = (attrs.get("property") or attrs.get("name") or "").lower()
            val = (attrs.get("content") or "").strip()
            if key in OG_KEYS and val and key not in found:
                found[key] = val
        for k in OG_KEYS:
            if k in found and download_image(urljoin(final, found[k]), dest):
                return host
    except Exception as err:
        print(f"[Cover] Gagal ambil og:image: {err}")
    return None

def select_news_with_cover(candidates: List[Dict[str, str]]) -> Tuple[Dict[str, str], List[str]]:
    if not candidates:
        candidates = [{
            "title": "Evaluasi Stabilisasi Pasokan dan Perkembangan Kebutuhan Pokok",
            "link": f"https://metrika.id/fallback/{get_now_wib().date()}",
            "summary": "Pemerintah memantau jalur logistik dan stabilitas harga komoditas pangan pokok di pasar eceran.",
            "published": str(get_now_wib().date()),
        }]
    chosen = candidates[0]
    for item in candidates[:6]:
        real = resolve_google_news_url(item["link"])
        domain = fetch_cover_from_article(real, SLIDE_IMG_PATHS["slide1"])
        if domain:
            item["cover_credit"] = domain
            item["real_link"] = real
            chosen = item
            print(f"[Cover] og:image berhasil dari {domain}: {item['title'][:70]}")
            break
    supporting = [c["title"] for c in candidates if c != chosen][:4]
    return chosen, supporting

def make_placeholder(path: Path) -> None:
    im = Image.new("RGB", (1200, 800), color=(43, 26, 18))
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, format="JPEG", quality=90)

def prepare_images(news_item: Dict[str, str]) -> Dict[str, Path]:
    cover = SLIDE_IMG_PATHS["slide1"]
    if not cover.exists():
        make_placeholder(cover)
    for k in ("slide2", "slide3", "slide4", "slide5"):
        target = SLIDE_IMG_PATHS[k]
        if not target.exists():
            shutil.copyfile(cover, target)
            news_item.setdefault("photo_sources", {})[k] = news_item.get("cover_credit") or "Dokumentasi Media"
    return dict(SLIDE_IMG_PATHS)

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

def extract_numeric_price(text: str) -> float:
    digits = re.sub(r"[^\d]", "", str(text or ""))
    return float(digits) if digits else 17500.0

def compute_indeks_keringat(price: float) -> Dict[str, str]:
    ojol_trips = max(1.0, round(price / 12500.0, 1))
    ojol_hours = max(0.5, round(ojol_trips * 0.75, 1))
    umr_hours = max(0.2, round(price / (5396763.0 / 22.0 / 8.0), 1))
    dpr_minutes = max(1.0, round(price / ((60000000.0 / 22.0 / 8.0) / 60.0), 1))
    return {
        "ojol": f"{ojol_trips:g} trip narik ({ojol_hours:g} jam di aspal)",
        "umr": f"{umr_hours:g} jam kerja",
        "dpr": f"{dpr_minutes:g} menit di ruang rapat",
    }

def analyze_with_gemini(news_item: Dict[str, str], prog_cfg: Dict[str, Any]) -> Dict[str, Any]:
    if not GEMINI_API_KEY:
        raise EnvironmentError("GEMINI_API_KEY belum terpasang di GitHub Secrets!")

    prog_id = prog_cfg["id"]
    prompt = f"""
Kamu adalah Jurnalis Data METRIKA (@metrika.id).
Ubah berita ini menjadi konten carousel 5 slide:
Judul: {news_item['title']}
Ringkasan: {news_item.get('summary', '')}
Program: {prog_cfg['name']} ({prog_cfg['subtitle']})

PEDOMAN INTEGRITAS:
- DILARANG mencantumkan angka persentase fiktif jika tidak tercantum di rilis berita asli.
- Rubrik {prog_id}: jangan campurkan jam kerja ojol jika bukan INDEKS_KERINGAT.
- Buat hook clickbait tajam, bungkus 2-4 kata kunci penting dengan <red>...</red>.
- 100% bebas dari emoji.

Format JSON murni:
{{
  "hook": "Judul Clickbait Tajam <red>Kata Kunci Merah</red>",
  "caption_lead": "Lead pembuka berita lugas (40-60 kata).",
  "caption_body": "Uraian fakta berita dan dampaknya (50-70 kata).",
  "caption_closing": "Gimana menurut lo soal fenomena ini? Tulis pendapat lo di komentar.",
  "hero_value": "Rp 104.000/kg",
  "hero_label": "harga riil di tingkat pasar eceran",
  "slide2_eyebrow": "KRONOLOGI & PERISTIWA",
  "slide2_hook": "Pertanyaan tajam penahan scroll",
  "slide2_paragraphs": ["Paragraf kronologi 1...", "Paragraf kronologi 2..."],
  "slide2_takeaway": "Catatan ringkas atas peristiwa.",
  "slide3_eyebrow": "BEDAH DATA & ANGKA",
  "slide3_hook": "Judul slide 3 penahan scroll",
  "slide3_metric_value": "Rp 104.000",
  "slide3_metric_label": "estimasi beban riil",
  "slide3_col1_title": "Pilar Lapangan",
  "slide3_col1_paragraph": "Penjelasan kondisi lapangan...",
  "slide3_col2_title": "Pilar Kebijakan",
  "slide3_col2_paragraph": "Penjelasan respon dinas/pemerintah...",
  "slide3_alert_text": "Catatan evaluasi kebijakan...",
  "chart_data": {{
    "title": "KOMPARASI DATA AUDIT",
    "items": [
      {{"label": "Kondisi Nyata Lapangan", "val_str": "Rp 104.000", "val": 104.0}},
      {{"label": "Patokan Acuan Regulasi", "val_str": "Rp 55.000", "val": 55.0}}
    ]
  }},
  "slide4_eyebrow": "REALITA DI LAPANGAN",
  "slide4_hook": "Tiga Realita Lapangan yang Dihadapi",
  "slide4_scenarios": [
    {{"tag": "MASYARAKAT BAWAH", "text": "**Pekerja Informal:** Penjelasan kondisi nyata..."}},
    {{"tag": "MANUVER BIROKRASI", "text": "**Langkah Regulator:** Penjelasan respon birokrasi..."}},
    {{"tag": "REALITA KEBIJAKAN", "text": "**Evaluasi Kebijakan:** Celah aturan..."}}
  ],
  "slide4_takeaway": "Kesimpulan realita lapangan.",
  "slide5_eyebrow": "KESIMPULAN & REFLEKSI",
  "slide5_hook": "Refleksi Akhir: <red>Bukan Sekadar Angka</red>",
  "verdict": "Catatan reflektif penutup redaksi yang tegas.",
  "slide5_highlights": [
    "Evaluasi konkret pertama.",
    "Evaluasi konkret kedua.",
    "Evaluasi konkret ketiga."
  ],
  "cta": "Pertanyaan reflektif untuk memantik diskusi audiens?",
  "sources": ["Portal Berita Terverifikasi Dewan Pers"]
}}
"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json"},
    }
    for model_name in PREFERRED_GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
        try:
            res = requests.post(url, json=payload, timeout=45)
            if res.status_code == 200:
                raw = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
                return strip_emoji_deep(json.loads(cleaned))
        except Exception:
            continue
    raise RuntimeError("Semua model Gemini gagal dihubungi.")

def build_metrika_content(analysis: Dict[str, Any], prog_cfg: Dict[str, Any], images: Dict[str, Path], news_item: Dict[str, str]) -> Dict[str, Any]:
    a = analysis
    cd = a.get("chart_data") or {"title": "DATA AUDIT", "items": [{"label": "Realisasi Lapangan", "val_str": "Riil", "val": 1.0}, {"label": "Target Otoritas", "val_str": "Target", "val": 1.0}]}
    chart_svg = generate_metric_svg_chart(cd.get("title", "KOMPARASI DATA AUDIT"), cd.get("items", []))
    price_val = extract_numeric_price(str(a.get("hero_value", "17500")))
    keringat_calc = compute_indeks_keringat(price_val)

    return {
        "program": prog_cfg["id"],
        "date": get_now_wib().strftime("%d %b %Y"),
        "hook": a.get("hook", "Analisis Data Hari Ini"),
        "caption_lead": a.get("caption_lead", news_item.get("summary", "")),
        "caption_body": a.get("caption_body", ""),
        "caption_closing": a.get("caption_closing", "Tulis pendapatmu di kolom komentar."),
        "hero": {"value": a.get("hero_value", ""), "label": a.get("hero_label", "")},
        "hero_image": str(images["slide1"]),
        "hero_image_credit": news_item.get("cover_credit", ""),
        "photo_sources": news_item.get("photo_sources", {}),
        "slide2_image": str(images["slide2"]),
        "slide3_image": str(images["slide3"]),
        "slide4_image": str(images["slide4"]),
        "slide5_image": str(images["slide5"]),
        "chart_svg": chart_svg,
        "keringat_calc": keringat_calc,
        "slide_context": {
            "eyebrow": a.get("slide2_eyebrow", "KRONOLOGI & PERISTIWA"),
            "hook": a.get("slide2_hook", "Kenapa Isu Ini Muncul?"),
            "paragraphs": a.get("slide2_paragraphs", [news_item.get("summary", "")]),
            "takeaway": a.get("slide2_takeaway", "Pokok peristiwa lapangan."),
        },
        "slide_metric": {
            "eyebrow": a.get("slide3_eyebrow", "BEDAH DATA & ANGKA"),
            "hook": a.get("slide3_hook", "Bedah Angka Kunci"),
            "metric_value": a.get("slide3_metric_value", a.get("hero_value", "")),
            "metric_label": a.get("slide3_metric_label", ""),
            "col1_title": a.get("slide3_col1_title", "Pilar Lapangan"),
            "col1_paragraph": a.get("slide3_col1_paragraph", ""),
            "col2_title": a.get("slide3_col2_title", "Pilar Kebijakan"),
            "col2_paragraph": a.get("slide3_col2_paragraph", ""),
            "alert_text": a.get("slide3_alert_text", "Catatan evaluasi kebijakan."),
        },
        "slide_strategy": {
            "eyebrow": a.get("slide4_eyebrow", "REALITA DI LAPANGAN"),
            "hook": a.get("slide4_hook", "Realita yang Dihadapi"),
            "scenarios": a.get("slide4_scenarios", []),
            "takeaway": a.get("slide4_takeaway", "Pokok masalah riil."),
        },
        "slide5_eyebrow": a.get("slide5_eyebrow", "KESIMPULAN & REFLEKSI"),
        "slide5_hook": a.get("slide5_hook", "Refleksi Akhir"),
        "verdict": a.get("verdict", "Catatan penutup redaksi."),
        "slide5_highlights": a.get("slide5_highlights", []),
        "cta": a.get("cta", "Gimana menurut lo?"),
        "sources": a.get("sources") or prog_cfg["sources"],
    }

def send_outputs_to_telegram(carousel_paths: List[Path], content: Dict[str, Any], news_item: Dict[str, str]) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Telegram] TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID belum diset di GitHub Secrets!")
        return

    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    clean_h = strip_emoji(re.sub(r"</?red>", "", content["hook"]))
    lead = content.get("caption_lead", "")
    body = content.get("caption_body", "")
    closing = content.get("caption_closing", "Tulis pendapat lo di komentar.")
    credit = content.get("hero_image_credit") or "Dokumentasi Media"
    news_link = news_item.get("real_link") or news_item["link"]

    keringat_lines = ""
    if content.get("program") == "INDEKS_KERINGAT":
        k = content.get("keringat_calc", {})
        if k:
            keringat_lines = (
                f"\n\n<b>Beban Waktu Kerja untuk Menebus Ini:</b>\n"
                f"• Driver Ojol: {k.get('ojol', '-')}\n"
                f"• Buruh UMR: {k.get('umr', '-')}\n"
                f"• Pejabat / Anggota DPR: {k.get('dpr', '-')}"
            )

    full_caption = (
        f"<b>{clean_h}</b>\n\n"
        f"{lead}\n\n"
        f"{body}"
        f"{keringat_lines}\n\n"
        f"{closing}\n\n"
        f"Sumber Foto: {credit}\n"
        f"Sumber Berita: <a href=\"{news_link}\">Liputan Lengkap</a>"
    )[:1020]

    if carousel_paths:
        with open(carousel_paths[0], "rb") as f_img:
            r = requests.post(
                f"{base_url}/sendPhoto",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": full_caption, "parse_mode": "HTML"},
                files={"photo": f_img},
                timeout=60,
            )
            if r.status_code == 200:
                print("[Telegram] Sukses kirim Single Photo Cover ke Telegram!")
            else:
                print(f"[Telegram] Gagal kirim foto: {r.text}")

    if len(carousel_paths) > 1:
        album_caption = f"<b>[CAROUSEL 5 SLIDE]</b>\n\n<b>{clean_h}</b>\n\n<i>Geser untuk membaca narasi visual lengkap (Slide 1–5).</i>"
        media_group, files_payload = [], {}
        for idx, img_path in enumerate(carousel_paths):
            key = f"slide_{idx}"
            files_payload[key] = img_path.open("rb")
            item = {"type": "photo", "media": f"attach://{key}"}
            if idx == 0:
                item["caption"] = album_caption
                item["parse_mode"] = "HTML"
            media_group.append(item)

        try:
            r_album = requests.post(
                f"{base_url}/sendMediaGroup",
                data={"chat_id": TELEGRAM_CHAT_ID, "media": json.dumps(media_group)},
                files=files_payload,
                timeout=120,
            )
            if r_album.status_code == 200:
                print("[Telegram] Sukses kirim Album Carousel ke Telegram!")
            else:
                print(f"[Telegram] Gagal kirim carousel: {r_album.text}")
        finally:
            for f in files_payload.values():
                f.close()

def main() -> None:
    prog_cfg = get_daily_program_config()
    print("=" * 72)
    print(f"MEMULAI PIPELINE: {MEDIA_NAME.upper()} | {prog_cfg['name']}")
    print("=" * 72)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CAROUSEL_DIR.mkdir(parents=True, exist_ok=True)

    candidates = fetch_candidates(prog_cfg)
    news_item, supporting = select_news_with_cover(candidates)
    analysis = analyze_with_gemini(news_item, prog_cfg)
    images = prepare_images(news_item)
    content = build_metrika_content(analysis, prog_cfg, images, news_item)

    (OUTPUT_DIR / "latest_analysis.json").write_text(
        json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("[Render] Merender 5 slide carousel via Playwright...")
    carousel_files = render_carousel_slides(content, CAROUSEL_DIR)
    print(f"[Render] Sukses: {len(carousel_files)} slide tersimpan.")

    send_outputs_to_telegram(carousel_files, content, news_item)
    save_posted_link(news_item["link"])
    print("PIPELINE SELESAI DENGAN SUKSES!")

if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"[ERROR] Pipeline gagal: {err}", file=sys.stderr)
        sys.exit(1)
