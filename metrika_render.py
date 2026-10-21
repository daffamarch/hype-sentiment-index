# ==============================================================================
# RENDERER SLIDE 1: COVER BERSIH TANPA PERSENTASE HALUSINASI
# ==============================================================================
def render_html_cover(content: Dict[str, Any], theme: Dict[str, Any], total_slides: int) -> str:
    hook_raw = content.get("hook", "")
    hook_formatted = format_hook_html(hook_raw)

    hero = content.get("hero", {})
    hero_val = html.escape(str(hero.get("value", ""))).replace("**", "").replace("*", "").strip()
    hero_lbl = format_point_body_html(str(hero.get("label", "")))
    date_str = html.escape(str(content.get("date", "21 OKT 2026"))).upper()

    img_uri = get_image_data_uri(content.get("hero_image"))
    s1_credit = format_photo_credit_text(
        content.get("hero_image_credit") or (content.get("photo_sources") or {}).get("slide1")
    )

    # ZERO HALUSINASI: Hanya tampilkan badge jika benar-benar ada data numerik riil
    stat_html = ""
    is_generic = any(g in hero_val.lower() for g in ["data kunci", "sorotan utama", "angka kunci", "data"])
    if hero_val and not is_generic:
        stat_html = f"""
        <div class="stat-pill-row">
          <div class="stat-pill">
            <span class="stat-num">{hero_val}</span>
            <span class="stat-lbl">{hero_lbl}</span>
          </div>
        </div>
        """

    photo_dom = f'<img src="{img_uri}" class="cover-photo" alt="Cover Visual" />' if img_uri else ""

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<style>
{get_base_css()}
</style>
</head>
<body>
  <div class="brand-header">
    <div class="brand-left">
      <div class="brand-monogram">M</div>
      <div class="brand-title-wrap">
        <div class="brand-title">METRIKA</div>
        <div class="brand-tagline">JURNALISME DATA & RISET FINANSIAL</div>
      </div>
    </div>
    <div class="program-chip">{date_str} • {theme['label']}</div>
  </div>

  <div class="cover-top-box">
    <h1 class="cover-headline">{hook_formatted}</h1>
    {stat_html}
  </div>

  <div class="cover-photo-wrapper">
    {photo_dom}
    <div class="photo-credit-badge">FOTO: {s1_credit}</div>
    <div class="photo-gradient-overlay" style="height: 120px; justify-content: flex-end; padding: 24px 52px;">
      <div style="color:rgba(250,246,240,0.8); font-size:13px; font-weight:800; letter-spacing:0.06em;">@metrika.id</div>
    </div>
  </div>
</body>
</html>
"""

# ==============================================================================
# RENDERER SLIDE 3: BEDAH DATA & IMPLIKASI (TERISOLASI PER RUBRIK)
# ==============================================================================
def render_html_metric(content: Dict[str, Any], theme: Dict[str, Any], total_slides: int) -> str:
    s3 = content.get("slide_metric", {})
    eyebrow = html.escape(s3.get("eyebrow", "BEDAH DATA & ANGKA"))
    hook = format_hook_html(s3.get("hook", "Berapa Triliun Rupiah yang Diam-diam Disedot dari Kantong Kita?"))

    # Hanya tampilkan kalkulator jam kerja/daya beli jika rubrik aktif adalah INDEKS_KERINGAT
    is_keringat_prog = (content.get("program") == "INDEKS_KERINGAT")
    keringat = content.get("keringat_calc", {}) if is_keringat_prog else {}
    keringat_html = ""
    if is_keringat_prog and keringat:
        keringat_html = f"""
        <div class="slide3-keringat-box">
          <div class="slide3-keringat-row"><span>Driver Ojol</span> <b>{html.escape(keringat.get('ojol', '-'))}</b></div>
          <div class="slide3-keringat-row"><span>Buruh UMR</span> <b>{html.escape(keringat.get('umr', '-'))}</b></div>
          <div class="slide3-keringat-row"><span>Anggota DPR</span> <b>{html.escape(keringat.get('dpr', '-'))}</b></div>
        </div>
        """

    s3_credit = format_photo_credit_text((content.get("photo_sources") or {}).get("slide3"), content.get("hero_image_credit"))
    img_uri = get_image_data_uri(content.get("slide3_image") or content.get("hero_image"))
    chart_svg = content.get("chart_svg")
    
    # Grafik SVG tidak memuat badge foto sama sekali
    if chart_svg:
        chart_or_img_dom = f'<div class="slide3-img-pane" style="position:relative; display:flex; align-items:center; justify-content:center; background:#22150E;">{chart_svg}</div>'
    else:
        credit_badge_dom = f'<div class="photo-credit-badge" style="top: 14px; right: 14px; padding: 4px 10px; font-size: 10px;">FOTO: {s3_credit}</div>'
        chart_or_img_dom = f'<div class="slide3-img-pane" style="position:relative;"><img src="{img_uri}" class="slide3-img" alt="Visual Analisis Data" />{credit_badge_dom}</div>' 

    # (Rendering 2 kolom narasi berbobot dan footer progress)
    # ...
