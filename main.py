# -*- coding: utf-8 -*-
"""Generador del portal de Esfigmomanómetros (Registros + Modelos LATU)."""

import os
import io
import pandas as pd
from folium import plugins
import folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable

# ==========================================================
# CONFIGURACIÓN
# ==========================================================
SHEET_REGISTROS_URL = "https://docs.google.com/spreadsheets/d/1iEJl5proYp_-wZHhXMPmzOdNfH4h6EHfDOi1ikCQsok/edit?usp=sharing"
SHEET_MODELOS_URL   = "https://docs.google.com/spreadsheets/d/14SxS9K7s0X4oMBK53P3uK4-oRLa8v1KU875NlhQTB7U/edit?usp=sharing"
CACHE_FILE = "coordenadas_cache.csv"

# ==========================================================
# 1. DATOS DE REGISTROS
# ==========================================================
archivo = "https://docs.google.com/spreadsheets/d/1iEJl5proYp_-wZHhXMPmzOdNfH4h6EHfDOi1ikCQsok/edit?usp=sharing"
sheet_id = archivo.split("/d/")[1].split("/")[0]
archivo_csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
df = pd.read_csv(archivo_csv_url)

df['Direccion_Completa'] = df['Dirección'].astype(str).str.strip() + ", Montevideo, Uruguay"

# ---------- CACHE ----------
if os.path.exists(CACHE_FILE):
    cache = pd.read_csv(CACHE_FILE)
    cache_map = dict(zip(cache['Direccion_Completa'], zip(cache['Latitud'], cache['Longitud'])))
    print(f"[Cache] {len(cache_map)} direcciones cargadas")
else:
    cache_map = {}

geolocator = Nominatim(
    user_agent="portal_esfigmomanometros_uy/1.0 (contacto: tu_email@ejemplo.com)",
    timeout=10
)
geocode = RateLimiter(
    geolocator.geocode,
    min_delay_seconds=1.2, max_retries=2,
    error_wait_seconds=5.0, swallow_exceptions=True
)

def geocodificar(direccion):
    if direccion in cache_map:
        return cache_map[direccion]
    try:
        loc = geocode(direccion)
        if loc:
            r = (loc.latitude, loc.longitude)
            cache_map[direccion] = r
            print(f"  ✓ {direccion[:60]}")
            return r
        return None
    except (GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable) as e:
        print(f"  ⚠ {e}")
        return None

print("\n[Geocoding] Resolviendo direcciones...")
df['Coords'] = df['Direccion_Completa'].apply(geocodificar)
df['Latitud']  = df['Coords'].apply(lambda c: c[0] if c else None)
df['Longitud'] = df['Coords'].apply(lambda c: c[1] if c else None)

pd.DataFrame(
    [(k, v[0], v[1]) for k, v in cache_map.items()],
    columns=['Direccion_Completa', 'Latitud', 'Longitud']
).to_csv(CACHE_FILE, index=False)

df_mapa = df.dropna(subset=['Latitud', 'Longitud']).copy()

# ==========================================================
# 2. MAPA
# ==========================================================
mapa = folium.Map(
    location=[-34.9011, -56.1645],
    zoom_start=12,
    tiles='OpenStreetMap',
    control_scale=True
)
plugins.Fullscreen(position='topright', title='Pantalla Completa', title_cancel='Salir').add_to(mapa)

for _, row in df_mapa.iterrows():
    nombre_empresa   = row.get('Razón Social', 'Empresa sin nombre')
    tipo_inscripcion = row.get('Inscripto como', 'Sin definir')
    origen           = row.get('Origen', 'Desconocido')

    html_popup = f"""
    <div style="font-family:'Inter','Segoe UI',Arial,sans-serif; min-width:240px; padding:4px;">
        <h4 style="margin:0 0 10px 0; color:#0f172a; font-size:15px; font-weight:700;">{nombre_empresa}</h4>
        <div style="background:#f1f5f9; padding:10px 12px; border-radius:8px; border-left:4px solid #0f4c81;">
            <b style="color:#64748b; font-size:10px; text-transform:uppercase;">Categoría</b><br>
            <span style="color:#0f172a; font-size:13px; font-weight:600;">{tipo_inscripcion}</span>
        </div>
        <div style="margin-top:10px; font-size:10px; color:#94a3b8; text-align:right; font-style:italic;">Fuente: {origen}</div>
    </div>"""

    color_pin = 'blue'
    t = str(tipo_inscripcion).lower()
    if 'importador reparador' in t or 'ambos' in t: color_pin = 'purple'
    elif 'importador' in t: color_pin = 'green'
    elif 'reparador'  in t: color_pin = 'orange'

    icono_forma = 'star' if origen == 'Sugerido por LATU' else 'info'

    folium.Marker(
        location=[row['Latitud'], row['Longitud']],
        popup=folium.Popup(html_popup, max_width=320),
        icon=folium.Icon(color=color_pin, icon=icono_forma, prefix='fa')
    ).add_to(mapa)

mapa_html_snippet = mapa._repr_html_()

# ==========================================================
# 3. MODELOS APROBADOS
# ==========================================================
if "REEMPLAZAR_ID_MODELOS" not in SHEET_MODELOS_URL:
    try:
        sid_m = SHEET_MODELOS_URL.split("/d/")[1].split("/")[0]
        url_m = f"https://docs.google.com/spreadsheets/d/{sid_m}/export?format=csv"
        df_modelos = pd.read_csv(url_m)
        print("[Modelos] Cargados desde planilla de Google Sheets")
    except Exception as e:
        print(f"[Modelos] Fallback a datos embebidos: {e}")
        df_modelos = pd.read_csv(io.StringIO(MODELOS_TSV), sep='\t')
else:
    df_modelos = pd.read_csv(io.StringIO(MODELOS_TSV), sep='\t')
    print(f"[Modelos] {len(df_modelos)} registros embebidos")

rename_map = {
    'Tipo de Instrumento': 'Tipo',
    'Nº Aprobación Modelo': 'Aprobacion',
    'N° Aprobación Modelo': 'Aprobacion',
    'Nº Aprobacion Modelo': 'Aprobacion',
    'Resolución': 'Aprobacion',
}
df_modelos = df_modelos.rename(columns=rename_map)

for col in ['Tipo', 'Marca', 'Modelo', 'Aprobacion']:
    if col not in df_modelos.columns:
        df_modelos[col] = '—'

df_modelos = df_modelos.drop_duplicates(subset=['Marca', 'Modelo']).reset_index(drop=True)
df_modelos = df_modelos.sort_values(['Marca', 'Modelo'], kind='stable').reset_index(drop=True)

# ==========================================================
# 4. GENERAR FILAS HTML
# ==========================================================
def build_modelos_rows(df_m) -> str:
    if df_m is None or df_m.empty:
        return """<tr><td colspan="3" class="text-center py-5">
            <div class="empty-state"><i class="fa-solid fa-clipboard-list"></i>
            <h5 class="mt-3 mb-1">Aún no hay modelos cargados</h5>
            <p class="text-muted small mb-0">Los registros aparecerán aquí automáticamente.</p>
            </div></td></tr>"""
    rows = []
    for _, r in df_m.iterrows():
        marca = str(r['Marca']).strip()
        modelo = str(r['Modelo']).strip()
        aprob  = str(r['Aprobacion']).strip()
        rows.append(f"""
        <tr>
            <td>
                <div class="d-flex align-items-center">
                    <div class="brand-avatar">{marca[:1].upper()}</div>
                    <span class="fw-semibold">{marca}</span>
                </div>
            </td>
            <td class="text-secondary">{modelo}</td>
            <td><span class="aprob-badge">{aprob}</span></td>
        </tr>""")
    return "".join(rows)

modelos_rows_html = build_modelos_rows(df_modelos)

marcas_unicas = sorted(df_modelos['Marca'].dropna().unique().tolist())
marcas_options = "".join(f'<option value="{m.lower()}">{m}</option>' for m in marcas_unicas)

total_modelos = len(df_modelos)
total_marcas  = df_modelos['Marca'].nunique()
tipo_principal = df_modelos['Tipo'].mode().iloc[0] if not df_modelos.empty else 'Esfigmomanómetro'

# ==========================================================
# 5. PLANTILLA HTML
# ==========================================================
pag_web_completa = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Esfigmomanómetros · Portal informativo</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
    :root {{
        --primary: #0f4c81; --primary-2: #1e6fbf; --accent: #00b4d8;
        --success: #10b981; --warning: #f59e0b; --danger: #ef4444; --purple: #8b5cf6;
        --gray-50: #f8fafc; --gray-100: #f1f5f9; --gray-200: #e2e8f0;
        --gray-400: #94a3b8; --gray-600: #64748b; --gray-800: #1e293b; --gray-900: #0f172a;
    }}
    * {{ -webkit-font-smoothing: antialiased; }}
    body {{ background: var(--gray-50); font-family: 'Inter', 'Segoe UI', system-ui, sans-serif; color: var(--gray-800); }}

    .hero-section {{
        background: linear-gradient(135deg, #0a3557 0%, #0f4c81 40%, #1e6fbf 75%, #00b4d8 100%);
        color: #fff; padding: 56px 0 44px; position: relative; overflow: hidden;
    }}
    .hero-section::before {{
        content: ""; position: absolute; inset: 0;
        background-image: radial-gradient(circle at 15% 30%, rgba(255,255,255,.12) 0%, transparent 45%),
                          radial-gradient(circle at 85% 75%, rgba(0,180,216,.25) 0%, transparent 45%);
        pointer-events: none;
    }}
    .hero-section::after {{
        content: ""; position: absolute; inset: 0;
        background-image: radial-gradient(rgba(255,255,255,.08) 1px, transparent 1px);
        background-size: 22px 22px; opacity: .35; pointer-events: none;
    }}
    .hero-inner {{ position: relative; z-index: 1; }}
    .hero-title {{ font-weight: 800; letter-spacing: -.02em; text-shadow: 0 2px 12px rgba(0,0,0,.15); }}
    .hero-subtitle {{ color: rgba(255,255,255,.85); font-weight: 400; }}

    /* Logo NIB en la cabecera */
    .nib-logo {{
        max-height: 100px;
        max-width: 100%;
        width: auto;
        filter: drop-shadow(0 4px 16px rgba(0,0,0,.35));
    }}

    .hero-chip {{
        display: inline-flex; align-items: center; gap: 8px;
        background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.22);
        backdrop-filter: blur(6px); padding: 6px 14px; border-radius: 999px;
        font-size: .8rem; font-weight: 500; margin-bottom: 16px;
    }}
    .hero-chip .dot {{
        width: 8px; height: 8px; border-radius: 50%; background: #4ade80;
        box-shadow: 0 0 0 4px rgba(74,222,128,.25); animation: pulse 2s infinite;
    }}
    @keyframes pulse {{
        0%,100% {{ box-shadow: 0 0 0 4px rgba(74,222,128,.25); }}
        50%     {{ box-shadow: 0 0 0 8px rgba(74,222,128,.05); }}
    }}

    .nav-tabs-custom {{ border-bottom: 1px solid var(--gray-200); gap: 4px; flex-wrap: nowrap; overflow-x: auto; }}
    .nav-tabs-custom::-webkit-scrollbar {{ display: none; }}
    .nav-tabs-custom .nav-link {{
        color: var(--gray-600); font-weight: 600; font-size: .92rem; border: none;
        background: transparent; padding: 14px 22px; border-radius: 10px 10px 0 0;
        position: relative; white-space: nowrap; transition: color .2s, background .2s;
    }}
    .nav-tabs-custom .nav-link:hover {{ color: var(--primary); background: rgba(15,76,129,.05); }}
    .nav-tabs-custom .nav-link.active {{ color: var(--primary); background: transparent; }}
    .nav-tabs-custom .nav-link.active::after {{
        content: ""; position: absolute; left: 12px; right: 12px; bottom: -1px;
        height: 3px; border-radius: 3px 3px 0 0;
        background: linear-gradient(90deg, var(--primary), var(--accent));
    }}

    .card-custom {{
        border: 1px solid var(--gray-200); border-radius: 16px; background: #fff;
        box-shadow: 0 1px 3px rgba(15,23,42,.04), 0 8px 24px rgba(15,23,42,.04);
        transition: box-shadow .3s ease; overflow: hidden;
    }}
    .card-custom:hover {{ box-shadow: 0 4px 12px rgba(15,23,42,.06), 0 16px 40px rgba(15,23,42,.08); }}
    .card-header-custom {{
        background: #fff; border-bottom: 1px solid var(--gray-100);
        font-weight: 700; color: var(--gray-900); padding: 18px 22px;
        display: flex; align-items: center; justify-content: space-between;
        flex-wrap: wrap; gap: 10px;
    }}
    .section-eyebrow {{
        font-size: .7rem; font-weight: 700; letter-spacing: .12em;
        text-transform: uppercase; color: var(--accent); margin-bottom: 6px;
    }}

    .map-container {{
        min-height: 580px; border-radius: 12px; overflow: hidden;
        border: 1px solid var(--gray-200); background: #fff;
    }}
    .legend {{
        display: flex; flex-wrap: wrap; gap: 14px; padding: 14px 18px;
        background: var(--gray-50); border: 1px solid var(--gray-200);
        border-radius: 12px; margin-bottom: 14px; font-size: .82rem;
    }}
    .legend-item {{ display: flex; align-items: center; gap: 8px; color: var(--gray-600); font-weight: 500; }}
    .legend-dot {{ width: 12px; height: 12px; border-radius: 50%; box-shadow: 0 0 0 2px #fff, 0 0 0 3px currentColor; }}

    .badge-soft {{
        display: inline-flex; align-items: center; padding: 5px 12px;
        border-radius: 999px; font-size: .75rem; font-weight: 600; white-space: nowrap;
    }}
    .badge-soft.secondary {{ background: var(--gray-100); color: var(--gray-600); }}

    .models-toolbar {{
        display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
        padding: 16px 22px; border-bottom: 1px solid var(--gray-100); background: #fff;
    }}
    .search-wrapper {{ position: relative; flex: 1 1 280px; min-width: 220px; }}
    .search-wrapper i {{
        position: absolute; left: 14px; top: 50%; transform: translateY(-50%);
        color: var(--gray-400); font-size: .9rem;
    }}
    .search-input {{
        width: 100%; padding: 10px 14px 10px 40px; border-radius: 10px;
        border: 1px solid var(--gray-200); background: var(--gray-50);
        font-size: .9rem; transition: border-color .2s, box-shadow .2s, background .2s;
    }}
    .search-input:focus {{
        outline: none; border-color: var(--primary-2); background: #fff;
        box-shadow: 0 0 0 4px rgba(30,111,191,.12);
    }}
    .models-table {{ width: 100%; border-collapse: separate; border-spacing: 0; font-size: .9rem; }}
    .models-table thead th {{
        background: var(--gray-50); color: var(--gray-600); font-size: .72rem;
        font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
        padding: 14px 18px; border-bottom: 1px solid var(--gray-200);
        text-align: left; white-space: nowrap;
    }}
    .models-table tbody td {{
        padding: 16px 18px; border-bottom: 1px solid var(--gray-100); vertical-align: middle;
    }}
    .models-table tbody tr:last-child td {{ border-bottom: none; }}
    .models-table tbody tr {{ transition: background .15s; }}
    .models-table tbody tr:hover {{ background: var(--gray-50); }}
    .brand-avatar {{
        width: 34px; height: 34px; border-radius: 9px;
        display: inline-flex; align-items: center; justify-content: center;
        background: linear-gradient(135deg, var(--primary), var(--accent));
        color: #fff; font-weight: 700; font-size: .85rem;
        margin-right: 10px; box-shadow: 0 4px 10px rgba(15,76,129,.18);
    }}
    .aprob-badge {{
        display: inline-flex; align-items: center; gap: 6px;
        background: rgba(0,180,216,.1); color: #0369a1;
        padding: 5px 12px; border-radius: 8px;
        font-size: .78rem; font-weight: 600; font-family: 'JetBrains Mono', monospace;
        border: 1px solid rgba(0,180,216,.2);
    }}
    .aprob-badge::before {{
        content: "\\f00c"; font-family: "Font Awesome 6 Free"; font-weight: 900;
        font-size: .65rem; color: var(--success);
    }}

    .empty-state {{ padding: 40px 20px; text-align: center; color: var(--gray-600); }}
    .empty-state i {{ font-size: 3rem; color: var(--gray-400); opacity: .6; }}

    .stat-card {{
        background: #fff; border: 1px solid var(--gray-200); border-radius: 14px;
        padding: 18px 20px; display: flex; align-items: center; gap: 14px;
        transition: transform .25s, box-shadow .25s;
    }}
    .stat-card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 24px rgba(15,23,42,.06); }}
    .stat-icon {{
        width: 46px; height: 46px; border-radius: 12px;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.15rem; color: #fff;
        background: linear-gradient(135deg, var(--primary), var(--primary-2)); flex-shrink: 0;
    }}
    .stat-icon.accent {{ background: linear-gradient(135deg, var(--accent), #48cae4); }}
    .stat-icon.purple {{ background: linear-gradient(135deg, var(--purple), #a78bfa); }}
    .stat-value {{ font-size: 1.4rem; font-weight: 800; color: var(--gray-900); line-height: 1; }}
    .stat-label {{ font-size: .78rem; color: var(--gray-600); margin-top: 4px; }}

    .metro-card {{
        border: 1px solid var(--gray-200); border-radius: 14px; background: #fff;
        padding: 22px; height: 100%;
        transition: transform .25s, box-shadow .25s, border-color .25s;
    }}
    .metro-card:hover {{
        transform: translateY(-3px); border-color: var(--primary-2);
        box-shadow: 0 12px 28px rgba(15,23,42,.08);
    }}
    .metro-card .icon-circle {{
        width: 44px; height: 44px; border-radius: 12px;
        display: inline-flex; align-items: center; justify-content: center;
        font-size: 1.1rem; margin-bottom: 14px;
    }}
    .icon-info    {{ background: rgba(0,180,216,.12);  color: var(--accent); }}
    .icon-success {{ background: rgba(16,185,129,.12); color: var(--success); }}
    .icon-warning {{ background: rgba(245,158,11,.15); color: var(--warning); }}

    .info-list {{ list-style: none; padding-left: 0; }}
    .info-list li {{
        padding-left: 28px; position: relative; margin-bottom: 10px;
        color: var(--gray-600); font-size: .93rem; line-height: 1.55;
    }}
    .info-list li::before {{
        content: "\\f00c"; font-family: "Font Awesome 6 Free"; font-weight: 900;
        position: absolute; left: 0; top: 1px; color: var(--accent); font-size: .8rem;
    }}
    .type-card {{
        border-radius: 12px; padding: 16px 18px; border: 1px solid var(--gray-200);
        background: var(--gray-50); margin-bottom: 12px;
        transition: border-color .2s, background .2s;
    }}
    .type-card:hover {{ background: #fff; border-color: var(--primary-2); }}
    .type-card h6 {{ font-weight: 700; margin-bottom: 6px; color: var(--gray-900); }}
    .type-card p  {{ font-size: .84rem; color: var(--gray-600); margin: 0; }}

    .nib-badge {{
        display: inline-flex; align-items: center; gap: 8px;
        background: linear-gradient(135deg, rgba(15,76,129,.08), rgba(0,180,216,.08));
        border: 1px solid rgba(15,76,129,.15);
        color: var(--primary); padding: 6px 14px; border-radius: 999px;
        font-size: .78rem; font-weight: 600;
    }}

    @media (max-width: 576px) {{
        .hero-section {{ padding: 40px 0 32px; }}
        .nav-tabs-custom .nav-link {{ padding: 12px 14px; font-size: .82rem; }}
        .models-table thead {{ display: none; }}
        .models-table tbody td {{ display: block; padding: 8px 16px; border-bottom: none; }}
        .models-table tbody tr {{ display: block; border-bottom: 1px solid var(--gray-100); padding: 8px 0; }}
        .nib-logo {{ max-height: 70px; }}
    }}
</style>
</head>
<body>

<div class="hero-section">
    <div class="container hero-inner">
        <div class="row align-items-center">
            <div class="col-lg-8">
                <span class="hero-chip"><span class="dot"></span> Portal actualizado automáticamente</span>
                <h1 class="display-5 hero-title mb-2">
                    <i class="fa-solid fa-heart-pulse me-3"></i>Esfigmomanómetros
                </h1>
                <p class="lead hero-subtitle mb-0">
                    Portal informativo sobre equipos de medición de presión arterial en Uruguay
                </p>
            </div>
            <div class="col-lg-4 text-lg-end text-center mt-4 mt-lg-0">
                <img src="https://www.nib1.fmed.edu.uy/sites/nib/files/2024-11/logo_nib_white_horiz-.png"
                     alt="Núcleo de Ingeniería Biomédica"
                     class="nib-logo"
                     onerror="this.style.display='none'; document.getElementById('nib-logo-fallback').style.display='inline-block';">
                <i id="nib-logo-fallback" class="fa-solid fa-stethoscope" style="display:none; font-size: 6rem; opacity: .15;"></i>
            </div>
        </div>
    </div>
</div>

<div class="container pb-5">
    <ul class="nav nav-tabs nav-tabs-custom mb-4" id="portalTabs" role="tablist">
        <li class="nav-item" role="presentation">
            <button class="nav-link active" id="mapa-tab" data-bs-toggle="tab" data-bs-target="#mapa-content" type="button" role="tab">
                <i class="fa-solid fa-map-location-dot me-2"></i>Mapa de Registros
            </button>
        </li>
        <li class="nav-item" role="presentation">
            <button class="nav-link" id="modelos-tab" data-bs-toggle="tab" data-bs-target="#modelos-content" type="button" role="tab">
                <i class="fa-solid fa-certificate me-2"></i>Modelos Aprobados <span class="badge-soft secondary ms-1">{total_modelos}</span>
            </button>
        </li>
        <li class="nav-item" role="presentation">
            <button class="nav-link" id="veripres-tab" data-bs-toggle="tab" data-bs-target="#veripres-content" type="button" role="tab">
                <i class="fa-solid fa-flask-vial me-2"></i>Proyecto VERIPRES
            </button>
        </li>
        <li class="nav-item" role="presentation">
            <button class="nav-link" id="info-tab" data-bs-toggle="tab" data-bs-target="#info-content" type="button" role="tab">
                <i class="fa-solid fa-book-medical me-2"></i>Información Técnica
            </button>
        </li>
        <li class="nav-item" role="presentation">
            <button class="nav-link" id="metro-tab" data-bs-toggle="tab" data-bs-target="#metro-content" type="button" role="tab">
                <i class="fa-solid fa-gauge me-2"></i>Metrología Legal
            </button>
        </li>
    </ul>

    <div class="tab-content" id="portalTabsContent">

        <!-- MAPA -->
        <div class="tab-pane fade show active" id="mapa-content" role="tabpanel">
            <div class="card card-custom">
                <div class="card-header-custom">
                    <div>
                        <div class="section-eyebrow">Directorio geográfico</div>
                        <div><i class="fa-solid fa-earth-americas text-primary me-2"></i>¿Dónde puedo llevar mi equipo?</div>
                    </div>
                    <span class="badge-soft secondary"><i class="fa-solid fa-location-dot me-1"></i> Total ubicados: {len(df_mapa)}</span>
                </div>
                <div class="card-body p-3">
                    <div class="legend">
                        <span class="legend-item"><span class="legend-dot" style="color:#28a745; background:#28a745;"></span> Importador</span>
                        <span class="legend-item"><span class="legend-dot" style="color:#fd7e14; background:#fd7e14;"></span> Reparador</span>
                        <span class="legend-item"><span class="legend-dot" style="color:#6f42c1; background:#6f42c1;"></span> Importador + Reparador</span>
                        <span class="legend-item"><i class="fa-solid fa-star text-secondary"></i> Sugerido por LATU</span>
                        <span class="legend-item"><i class="fa-solid fa-circle-info text-secondary"></i> Otras fuentes</span>
                    </div>
                    <div class="map-container">{mapa_html_snippet}</div>
                </div>
            </div>
        </div>

        <!-- MODELOS APROBADOS -->
        <div class="tab-pane fade" id="modelos-content" role="tabpanel">
            <div class="row g-3 mb-4">
                <div class="col-md-4">
                    <div class="stat-card">
                        <div class="stat-icon"><i class="fa-solid fa-list-check"></i></div>
                        <div>
                            <div class="stat-value">{total_modelos}</div>
                            <div class="stat-label">Modelos aprobados</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="stat-card">
                        <div class="stat-icon accent"><i class="fa-solid fa-tags"></i></div>
                        <div>
                            <div class="stat-value">{total_marcas}</div>
                            <div class="stat-label">Marcas comerciales</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="stat-card">
                        <div class="stat-icon purple"><i class="fa-solid fa-shield-halved"></i></div>
                        <div>
                            <div class="stat-value" style="font-size:1rem;">{tipo_principal}</div>
                            <div class="stat-label">Tipo de instrumento</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card card-custom">
                <div class="card-header-custom">
                    <div>
                        <div class="section-eyebrow">Control metrológico · LATU</div>
                        <div><i class="fa-solid fa-certificate text-primary me-2"></i>Modelos de esfigmomanómetros aprobados</div>
                    </div>
                    <span class="badge-soft secondary"><i class="fa-solid fa-circle-check me-1"></i> Vigentes</span>
                </div>

                <div class="models-toolbar">
                    <div class="search-wrapper">
                        <i class="fa-solid fa-magnifying-glass"></i>
                        <input type="text" id="modelSearch" class="search-input" placeholder="Buscar por marca, modelo o Nº de aprobación...">
                    </div>
                    <select id="brandFilter" class="form-select" style="max-width: 220px; border-radius: 10px; border-color: var(--gray-200);">
                        <option value="">Todas las marcas</option>
                        {marcas_options}
                    </select>
                </div>

                <div class="table-responsive">
                    <table class="models-table" id="modelsTable">
                        <thead>
                            <tr>
                                <th>Marca</th>
                                <th>Modelo</th>
                                <th>Nº Aprobación</th>
                            </tr>
                        </thead>
                        <tbody>
                            {modelos_rows_html}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- PROYECTO VERIPRES -->
        <div class="tab-pane fade" id="veripres-content" role="tabpanel">
            <div class="row g-3">
                <div class="col-lg-7">
                    <div class="card card-custom p-4 p-md-5 h-100">
                        <div class="section-eyebrow">Núcleo de Ingeniería Biomédica · UdelaR</div>
                        <h3 class="fw-bold mb-3" style="color: var(--gray-900);">¿Qué es el Proyecto VERIPRES?</h3>
                        <p class="text-secondary" style="line-height: 1.7;">
                            <strong style="color: var(--primary);">VERIPRES</strong> es una iniciativa del <strong>Núcleo de Ingeniería Biomédica (NIB)</strong> de las Facultades de Medicina e Ingeniería de la Universidad de la República. Su objetivo es contribuir al control de la hipertensión arterial en Uruguay mediante la promoción del uso de esfigmomanómetros validados y el fortalecimiento de la red de servicios técnicos autorizados.
                        </p>
                        <p class="text-secondary" style="line-height: 1.7;">
                            El proyecto se alinea con el marco regulatorio nacional, que exige que los equipos de medición de presión arterial cuenten con aprobación de modelo y verificación periódica por parte del Laboratorio Tecnológico del Uruguay (LATU). VERIPRES busca que tanto profesionales de la salud como la población general puedan identificar fácilmente qué equipos son confiables y dónde pueden ser mantenidos o reparados.
                        </p>
                        <h5 class="fw-bold mt-4 mb-3" style="color: var(--gray-900);">
                            <i class="fa-solid fa-bullseye text-primary me-2"></i>Objetivos principales
                        </h5>
                        <ul class="info-list mt-3">
                            <li>Promover el uso de esfigmomanómetros con aprobación de modelo vigente.</li>
                            <li>Facilitar el acceso a la verificación periódica obligatoria de los equipos en uso.</li>
                            <li>Visibilizar la red de importadores y talleres de reparación autorizados.</li>
                            <li>Educar sobre la importancia de la exactitud en la medición de la presión arterial.</li>
                        </ul>
                    </div>
                </div>
                <div class="col-lg-5">
                    <div class="card card-custom p-4 h-100">
                        <div class="section-eyebrow">Criterios técnicos</div>
                        <h5 class="fw-bold mb-3" style="color: var(--gray-900);">Equipos y tolerancia</h5>

                        <div class="type-card mb-3">
                            <h6><i class="fa-solid fa-check-circle text-success me-2"></i>Equipos incluidos</h6>
                            <p class="mb-0">El portal se enfoca en <strong>esfigmomanómetros no invasivos</strong>, tanto de tipo <strong>mecánico (aneroide)</strong> como <strong>automático (digital)</strong>.</p>
                        </div>

                        <div class="type-card">
                            <h6><i class="fa-solid fa-ruler-combined text-primary me-2"></i>Error máximo permitido (EMP)</h6>
                            <p class="mb-0">
                                El criterio de aceptación se basa en la reglamentación técnica nacional. Para la <strong>verificación de equipos en uso</strong>, el error máximo admisible es de <strong>± 4 mmHg</strong>.
                            </p>
                        </div>

                        <p class="text-secondary small mt-3 mb-0" style="line-height: 1.6;">
                            <strong>Base normativa:</strong> Este valor se establece en el <strong>Decreto N° 446/009</strong> (esfigmomanómetros mecánicos) y en el <strong>Decreto N° 24/011</strong> (automáticos), que incorporan la Recomendación Internacional <strong>OIML R 16-1</strong>. La aprobación de modelo y la primera verificación son más estrictas (≈ ± 3 mmHg).
                        </p>
                    </div>
                </div>
            </div>
        </div>

        <!-- INFO TÉCNICA -->
        <div class="tab-pane fade" id="info-content" role="tabpanel">
            <div class="row g-3">
                <div class="col-lg-8">
                    <div class="card card-custom p-4 p-md-5 h-100">
                        <div class="section-eyebrow">Fundamentos clínicos</div>
                        <h3 class="fw-bold mb-3" style="color: var(--gray-900);">¿Qué es un Esfigmomanómetro?</h3>
                        <p class="text-secondary" style="line-height: 1.7;">
                            El <strong style="color: var(--primary);">esfigmomanómetro</strong>, conocido comúnmente como tensiómetro,
                            es un instrumento de medición médica utilizado para la determinación no invasiva de la presión arterial
                            sistólica y diastólica. Es una herramienta crítica en el diagnóstico y monitoreo de condiciones
                            cardiovasculares como la hipertensión arterial.
                        </p>
                        <h5 class="fw-bold mt-4 mb-3" style="color: var(--gray-900);">
                            <i class="fa-solid fa-gears text-primary me-2"></i>¿Cómo funciona?
                        </h5>
                        <p class="text-secondary" style="line-height: 1.7;">
                            El principio se basa en la oclusión parcial o total de una arteria superficial (generalmente la arteria
                            braquial en el brazo) mediante un brazalete inflable neumático. Al inflar el brazalete por encima de la
                            presión sistólica del paciente, el flujo sanguíneo se detiene. Luego, el aire se libera lentamente
                            disminuyendo la presión de forma controlada:
                        </p>
                        <ul class="info-list mt-3">
                            <li><strong>Presión Sistólica (Máxima):</strong> Se identifica cuando la presión del brazalete baja lo suficiente como para permitir que la sangre comience a pasar de nuevo, generando el primer sonido pulsátil audible (primer Ruido de Korotkoff).</li>
                            <li><strong>Presión Diastólica (Mínima):</strong> Se registra en el momento exacto en que los ruidos arteriales desaparecen por completo, indicando que el flujo de sangre ha vuelto a ser laminar y continuo.</li>
                        </ul>
                    </div>
                </div>
                <div class="col-lg-4">
                    <div class="card card-custom p-4 h-100">
                        <div class="section-eyebrow">Clasificación</div>
                        <h5 class="fw-bold mb-3" style="color: var(--gray-900);">Tipos de equipos</h5>
                        <div class="type-card">
                            <h6><i class="fa-solid fa-compass text-warning me-2"></i>Aneroides</h6>
                            <p>Sistema mecánico de fuelle interno y aguja sobre dial graduado. Propensos a descalibrarse ante impactos.</p>
                        </div>
                        <div class="type-card">
                            <h6><i class="fa-solid fa-vial text-danger me-2"></i>De mercurio</h6>
                            <p>Patrón de oro clínico histórico. En desuso por riesgo ambiental y toxicidad ante rotura.</p>
                        </div>
                        <div class="type-card mb-0">
                            <h6><i class="fa-solid fa-microchip text-success me-2"></i>Digitales</h6>
                            <p>Método oscilométrico automático con transductores electrónicos. Requieren algoritmos validados clínicamente.</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- METROLOGÍA -->
        <div class="tab-pane fade" id="metro-content" role="tabpanel">
            <div class="card card-custom p-4 p-md-5">
                <div class="section-eyebrow">Calidad y normativa</div>
                <h3 class="fw-bold mb-2" style="color: var(--gray-900);">Aseguramiento de la Calidad Metrológica</h3>
                <p class="text-secondary mb-4" style="max-width: 900px; line-height: 1.7;">
                    Dado que los errores de medición en medicina pueden inducir a diagnósticos erróneos o medicaciones
                    equivocadas, estos dispositivos están sujetos a normativas estrictas de control metrológico.
                </p>
                <div class="row g-3">
                    <div class="col-md-4">
                        <div class="metro-card">
                            <div class="icon-circle icon-info"><i class="fa-solid fa-scale-balanced"></i></div>
                            <h5 class="fw-bold mb-2" style="color: var(--gray-900); font-size: 1.05rem;">Calibración</h5>
                            <p class="text-secondary small mb-0" style="line-height: 1.65;">
                                Proceso técnico que compara los valores indicados por el tensiómetro bajo prueba contra
                                un manómetro patrón certificado de alta precisión. El resultado determina el error del
                                instrumento, plasmado en un certificado de calibración.
                            </p>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="metro-card">
                            <div class="icon-circle icon-success"><i class="fa-solid fa-square-check"></i></div>
                            <h5 class="fw-bold mb-2" style="color: var(--gray-900); font-size: 1.05rem;">Verificación</h5>
                            <p class="text-secondary small mb-0" style="line-height: 1.65;">
                                Acto de control legal obligatorio ejecutado por la autoridad competente (alineado con LATU)
                                para certificar si el instrumento se encuentra dentro de los Errores Máximos Permitidos (EMP),
                                aprobando o rechazando su uso clínico.
                            </p>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="metro-card">
                            <div class="icon-circle icon-warning"><i class="fa-solid fa-wrench"></i></div>
                            <h5 class="fw-bold mb-2" style="color: var(--gray-900); font-size: 1.05rem;">Reparación</h5>
                            <p class="text-secondary small mb-0" style="line-height: 1.65;">
                                Mantenimiento correctivo realizado por talleres autorizados ante fugas en tuberías o pera,
                                fallas en la válvula de purga o desvíos mecánicos severos. Un equipo reparado debe
                                recalibrarse y verificarse obligatoriamente antes de volver a operar.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>

    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script>
    (function () {{
        const searchInput = document.getElementById('modelSearch');
        const brandFilter = document.getElementById('brandFilter');
        const rows        = document.querySelectorAll('#modelsTable tbody tr');

        function filterRows() {{
            const term  = (searchInput?.value || '').toLowerCase().trim();
            const brand = (brandFilter?.value || '').toLowerCase();

            rows.forEach(row => {{
                if (row.querySelector('.empty-state')) return;
                const text = row.textContent.toLowerCase();
                const matchesTerm  = !term  || text.includes(term);
                const matchesBrand = !brand || text.includes(brand);
                row.style.display = (matchesTerm && matchesBrand) ? '' : 'none';
            }});
        }}

        searchInput?.addEventListener('input', filterRows);
        brandFilter?.addEventListener('change', filterRows);
    }})();
</script>
</body>
</html>
"""

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(pag_web_completa)

print(f"✅ index.html generado con {total_modelos} modelos y {len(df_mapa)} ubicaciones.")
