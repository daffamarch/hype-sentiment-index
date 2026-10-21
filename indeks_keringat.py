#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
indeks_keringat.py -- Modul Kalkulator Daya Beli & Beban Waktu Kerja Riil (METRIKA)

Fungsi:
Menghitung konversi harga barang / gaya hidup / biaya pokok menjadi jam kerja keringat nyata
antara Driver Ojol (aspal) vs Pekerja UMR (kantor/pabrik) vs Anggota DPR (ruang sidang).
"""

from typing import Dict, Any
import re

# Parameter Ekonomi Acuan:
# 1. Driver Ojol: Laba bersih rata-rata per trip Rp 12.500. Asumsi 1 trip = 45 menit (0.75 jam) di aspal.
OJOL_TRIP_NET = 12500.0
OJOL_HOURS_PER_TRIP = 0.75

# 2. Pekerja UMR Jakarta: Rp 5.396.763 / bulan (22 hari kerja, 8 jam/hari = 176 jam kerja/bulan)
UMR_MONTHLY = 5396763.0
UMR_DAILY = UMR_MONTHLY / 22.0
UMR_HOURLY = UMR_DAILY / 8.0

# 3. Anggota DPR RI: Gaji pokok + Aneka Tunjangan Resmi ~Rp 60.000.000 / bulan
# (22 hari kerja = Rp 2.727.272/hari = Rp 340.909/jam = Rp 5.681/menit)
DPR_MONTHLY = 60000000.0
DPR_DAILY = DPR_MONTHLY / 22.0
DPR_HOURLY = DPR_DAILY / 8.0
DPR_MINUTE = DPR_HOURLY / 60.0


def extract_price(text_or_number: Any) -> float:
    """Mengekstrak angka nominal harga rupiah dari teks bebas."""
    if isinstance(text_or_number, (int, float)):
        return float(text_or_number)
    digits = re.sub(r"[^\d]", "", str(text_or_number or ""))
    if digits:
        try:
            return float(digits)
        except ValueError:
            pass
    return 17500.0


def hitung_indeks_keringat(item_name: str, price: float) -> Dict[str, Any]:
    """
    Menghitung beban waktu kerja untuk membeli 1 unit barang.
    Mengembalikan data metrik terformat untuk visual dan caption.
    """
    price = max(100.0, float(price))

    # 1. Driver Ojol
    ojol_trips = max(1.0, round(price / OJOL_TRIP_NET, 1))
    ojol_hours = max(0.1, round(ojol_trips * OJOL_HOURS_PER_TRIP, 1))
    ojol_days = max(0.1, round(ojol_hours / 10.0, 1))  # Asumsi 10 jam narik per hari

    # 2. Pekerja UMR
    umr_hours = max(0.1, round(price / UMR_HOURLY, 1))
    umr_days = max(0.1, round(price / UMR_DAILY, 2))
    umr_pct_salary = min(100.0, round((price / UMR_MONTHLY) * 100, 1))

    # 3. Anggota DPR
    dpr_minutes = max(0.1, round(price / DPR_MINUTE, 1))
    dpr_hours = max(0.01, round(price / DPR_HOURLY, 2))

    summary_text = (
        f"Untuk membeli {item_name} seharga Rp {price:,.0f}:\n"
        f"• Driver Ojol: butuh narik {ojol_trips:g} trip ({ojol_hours:g} jam di aspal)\n"
        f"• Pekerja UMR: butuh {umr_hours:g} jam kerja ({umr_days:g} hari kerja)\n"
        f"• Anggota DPR: cukup duduk {dpr_minutes:g} menit di ruang sidang"
    ).replace(",", ".")

    return {
        "item_name": item_name,
        "price": price,
        "price_formatted": f"Rp {price:,.0f}".replace(",", "."),
        "ojol": {
            "trips": ojol_trips,
            "hours": ojol_hours,
            "days": ojol_days,
            "display": f"{ojol_trips:g} trip narik ({ojol_hours:g} jam di aspal)",
        },
        "umr": {
            "hours": umr_hours,
            "days": umr_days,
            "pct_monthly": umr_pct_salary,
            "display": f"{umr_hours:g} jam kerja ({umr_days:g} hari kerja)",
        },
        "dpr": {
            "minutes": dpr_minutes,
            "hours": dpr_hours,
            "display": f"{dpr_minutes:g} menit kerja di ruang sidang",
        },
        "summary": summary_text,
    }


if __name__ == "__main__":
    import sys
    nama = sys.argv[1] if len(sys.argv) > 1 else "iPhone 16 Pro Max"
    nominal = float(sys.argv[2]) if len(sys.argv) > 2 else 25000000.0
    res = hitung_indeks_keringat(nama, nominal)
    print("=" * 60)
    print("HASIL KALKULASI INDEKS KERINGAT METRIKA")
    print("=" * 60)
    print(res["summary"])
