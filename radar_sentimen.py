#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
radar_sentimen.py -- Modul Analisis Polarisasi Kebijakan Publik & Sentimen (METRIKA)

Fungsi:
Membedah respon kritis dan perdebatan ruang publik atas kebijakan kementerian/pemerintah
dibandingkan dengan klaim resmi yang disampaikan oleh pejabat publik secara akurat dan berbasis fakta.
ZERO HALUSINASI: Dilarang mengarang persentase survei sintetis bila tidak bersumber dari rilis lembaga survei resmi.
"""

from typing import Dict, Any, List, Optional
import re

def analisis_polarisasi_sentimen(
    judul_isu: str,
    klaim_pejabat: str,
    fakta_lapangan: str,
    data_survei_resmi: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Menyusun analisis komparasi sentimen polarisasi publik atas kebijakan.
    Hanya menyajikan angka persentase jika data rilis resmi lembaga survei/BPS disertakan.
    """
    chart_items = []
    if data_survei_resmi and isinstance(data_survei_resmi, dict):
        for k, v in data_survei_resmi.items():
            chart_items.append({"label": k, "val_str": f"{v:g}%", "val": float(v)})
    else:
        # Tampilan komparatif kualitatif berbasis pilar isu riil (bukan persentase karangan)
        chart_items = [
            {"label": "Klaim Pejabat / Target Regulasi", "val_str": "Klaim Resmi", "val": 50.0},
            {"label": "Catatan Lapangan & Audit Publik", "val_str": "Sorotan Kritis", "val": 50.0},
        ]

    return {
        "judul_isu": judul_isu,
        "klaim_pejabat": klaim_pejabat,
        "fakta_lapangan": fakta_lapangan,
        "chart_items": chart_items,
        "headline_polarisasi": f"Klaim Pejabat vs Fakta Lapangan: {judul_isu}",
        "poin_evaluasi": [
            "Kesenjangan antara rilis pers formal dengan realitas yang dirasakan masyarakat di lapangan.",
            "Tuntutan transparansi alokasi anggaran dan pengawasan implementasi program di tingkat daerah.",
            "Pentingnya keterbukaan kanal masukan masyarakat sebelum kebijakan diputuskan sepihak.",
        ],
    }

if __name__ == "__main__":
    import sys
    isu = sys.argv[1] if len(sys.argv) > 1 else "Kenaikan Pajak & Efisiensi Anggaran"
    klaim = sys.argv[2] if len(sys.argv) > 2 else "Pemerintah menjamin kenaikan tarif demi stabilitas fiskal negara."
    fakta = sys.argv[3] if len(sys.argv) > 3 else "Publik menuntut audit tunjangan pejabat mewah sebelum menaikkan pajak rakyat."
    res = analisis_polarisasi_sentimen(isu, klaim, fakta)
    print("=" * 60)
    print("HASIL ANALISIS RADAR SENTIMEN METRIKA (AKURAT & ZERO HALUSINASI)")
    print("=" * 60)
    print(f"Topik: {res['judul_isu']}")
    print(f"Klaim Otoritas: {res['klaim_pejabat']}")
    print(f"Catatan Lapangan: {res['fakta_lapangan']}")
    print("Item Visual Komparasi:", res["chart_items"])
