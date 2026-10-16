# -*- coding: utf-8 -*-
"""Generador del portal de Esfigmomanómetros (Registros + Modelos LATU)."""

import pandas as pd
from folium import plugins
import folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# ==========================================================
# CONFIGURACIÓN: pegá aquí el link de la nueva planilla de modelos aprobados
# cuando la tengas creada. Si la dejás vacía o con el placeholder,
# el portal mostrará un estado "pendiente" elegante.
# ==========================================================
SHEET_MODELOS_URL = "https://docs.google.com/spreadsheets/d/14SxS9K7s0X4oMBK53P3uK4-oRLa8v1KU875NlhQTB7U/edit?usp=sharing"

# ==========================================================
# 1. DATOS DE REGISTROS (Importadores / Reparadores)
# ==========================================================
archivo = "https://docs.google.com/spreadsheets/d/1iEJl5proYp_-wZHhXMPmzOdNfH4h6EHfDOi1ikCQsok/edit?usp=sharing"
sheet_id = archivo.split("/d/")[1].split("/")[0]
archivo_csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
df = pd.read_csv(archivo_csv_url)

geolocator = Nominatim(user_agent="mapa_registros_colab")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.5)

df['Direccion_Completa'] = df['Dirección'].astype(str) + ", Montevideo, Uruguay"
df['Ubicacion'] = df['Direccion_Completa'].apply(geocode)
df['Latitud']  = df['Ubicacion'].apply(lambda loc: loc.latitude  if loc else None)
df['Longitud'] = df['Ubicacion'].apply(lambda loc: loc.longitude if loc else None)
df_mapa = df.dropna(subset=['Latitud', 'Longitud']).copy()

mapa = folium.Map(
    location=[-34.9011, -56.1645],
    zoom_start=12,
    tiles='CartoDB positron',
    control_scale=True
)
plugins.Fullscreen(position='topright', title='Pantalla Completa', title_cancel='Salir').add_to(mapa)

for index, row in df_mapa.iterrows():
    nombre_empresa   = row.get('Razón Social', 'Empresa sin nombre')
    tipo_inscripcion = row.get('Inscripto como', 'Sin definir')
    origen           = row.get('Origen', 'Desconocido')

    html_popup = f"""
    <div style="font-family: 'Inter','Segoe UI',Arial,sans-serif; min-width:240px; padding:4px;">
        <h4 style="margin:0 0 10px 0; color:#0f172a; font-size:15px; font-weight:700;">{nombre_empresa}</h4>
        <div style="background:#f1f5f9; padding:10px 12px; border-radius:8px; border-left:4px solid #0f4c81;">
            <b style="color:#64748b; font-size:10px; text-transform:uppercase; letter-spacing:.5px;">Categoría</b><br>
            <span style="color:#0f172a; font-size:13px; font-weight:600;">{tipo_inscripcion}</span>
        </div>
        <div style="margin-top:10px; font-size:10px; color:#94a3b8; text-align:right; font-style:italic;">
            Fuente: {origen}
        </div>
    </div>
    """

    color_pin = 'blue'
    t = str(tipo_inscripcion).lower()
    if 'importador reparador' in t or 'ambos' in t:
        color_pin = 'purple'
    elif 'importador' in t:
        color_pin = 'green'
    elif 'reparador' in t:
        color_pin = 'orange'

    icono_forma = 'star' if origen == 'Sugerido por LATU' else 'info'

    folium.Marker(
        location=[row['Latitud'], row['Longitud']],
        popup=folium.Popup(html_popup, max_width=320),
        icon=folium.Icon(color=color_pin, icon=icono_forma, prefix='fa')
    ).add_to(mapa)

mapa_html_snippet = mapa._repr_html_()

# ==========================================================
# 2. DATOS DE MODELOS APROBADOS POR LATU (opcional)
# Columnas esperadas en la planilla:
#   Marca | Modelo | Tipo | Resolución | Fecha | Estado
# ==========================================================
df_modelos = None
if "REEMPLAZAR_ID_MODELOS" not in SHEET_MODELOS_URL:
    try:
        sid_m = SHEET_MODELOS_URL.split("/d/")[1].split("/")[0]
        url_m = f"https://docs.google.com/spreadsheets/d/{sid_m}/export?format=csv"
        df_modelos = pd.read_csv(url_m)
    except Exception as e:
        print(f"[Info] No se pudieron cargar modelos aprobados: {e}")
        df_modelos = None


def _badge_estado(estado: str) -> str:
    e = (estado or "").lower()
    if "aprob" in e or "vigente" in e:
        return "success"
    if "vencid" in e or "caduc" in e:
        return "warning"
    if "suspend" in e or "rechaz" in e:
        return "danger"
    return "secondary"


def _icono_tipo(tipo: str) -> str:
    t = (tipo or "").lower()
    if "digital" in t:
        return "fa-microchip"
    if "mercurio" in t:
        return "fa-vial"
    return "fa-compass"


def build_modelos_rows(df_m) -> str:
    if df_m is None or df_m.empty:
        return """
            <tr>
                <td colspan="6" class="text-center py-5">
                    <div class="empty-state">
                        <i class="fa-solid fa-clipboard-list"></i>
                        <h5 class="mt-3 mb-1">Aún no hay modelos cargados</h5>
                        <p class="text-muted small mb-0">
                            La planilla de modelos aprobados por LATU está pendiente de conexión.<br>
                            Los registros aparecerán aquí automáticamente.
                        </p>
                    </div>
                </td>
            </tr>"""

    rows = []
    for _, r in df_m.iterrows():
        marca      = str(r.get('Marca', '—')).strip()
        modelo     = str(r.get('Modelo', '—')).strip()
        tipo       = str(r.get('Tipo', '—')).strip()
        resolucion = str(r.get('Resolución', r.get('Resolucion', r.get('N° Resolución', '—')))).strip()
        fecha      = str(r.get('Fecha', r.get('Fecha Aprobación', '—'))).strip()
        estado     = str(r.get('Estado', 'Aprobado')).strip()

        rows.append(f"""
            <tr>
                <td>
                    <div class="d-flex align-items-center">
                        <div class="brand-avatar">{marca[:1].upper()}</div>
                        <span class="fw-semibold">{marca}</span>
                    </div>
                </td>
                <td class="text-secondary">{modelo}</td>
                <td><i class="fa-solid {_icono_tipo(tipo)} me-2 text-primary"></i>{tipo}</td>
                <td><span class="text-muted small">{resolucion}</span></td>
                <td><span class="text-muted small">{fecha}</span></td>
                <td><span class="badge-soft {_badge_estado(estado)}">{estado}</span></td>
            </tr>""")
    return "".join(rows)


modelos_rows_html = build_modelos_rows(df_modelos)

# Estadísticas rápidas para la cabecera de la sección
total_modelos = 0 if df_modelos is None else len(df_modelos)
total_marcas  = 0 if df_modelos is None else df_modelos['Marca'].nunique() if 'Marca' in df_modelos.columns else 0

# ==========================================================
# 3. PLANTILLA HTML (diseño moderno)
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
        --primary: #0f4c81;
        --primary-2: #1e6fbf;
        --accent: #00b4d8;
        --success: #10b981;
        --warning: #f59e0b;
        --danger: #ef4444;
        --purple: #8b5cf6;
        --gray-50: #f8fafc;
        --gray-100: #f1f5f9;
        --gray-200: #e2e8f0;
        --gray-400: #94a3b8;
        --gray-600: #64748b;
        --gray-800: #1e293b;
        --gray-900: #0f172a;
    }}
    * {{ -webkit-font-smoothing: antialiased; }}
    body {{
        background: var(--gray-50);
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
        color: var(--gray-800);
    }}

    /* ---------- HERO ---------- */
    .hero-section {{
        background: linear-gradient(135deg, #0a3557 0%, #0f4c81 40%, #1e6fbf 75%, #00b4d8 100%);
        color: #fff;
        padding: 56px 0 44px;
        position: relative;
        overflow: hidden;
    }}
    .hero-section::before {{
        content: "";
        position: absolute; inset: 0;
        background-image:
            radial-gradient(circle at 15% 30%, rgba(255,255,255,.12) 0%, transparent 45%),
            radial-gradient(circle at 85% 75%, rgba(0,180,216,.25) 0%, transparent 45%);
        pointer-events: none;
    }}
    .hero-section::after {{
        content: "";
        position: absolute; inset: 0;
        background-image: radial-gradient(rgba(255,255,255,.08) 1px, transparent 1px);
        background-size: 22px 22px;
        opacity: .35;
        pointer-events: none;
    }}
    .hero-inner {{ position: relative; z-index: 1; }}
    .hero-title {{
        font-weight: 800; letter-spacing: -.02em;
        text-shadow: 0 2px 12px rgba(0,0,0,.15);
    }}
    .hero-subtitle {{ color: rgba(255,255,255,.85); font-weight: 400; }}
    .hero-chip {{
        display: inline-flex; align-items: center; gap: 8px;
        background: rgba(255,255,255,.14);
        border: 1px solid rgba(255,255,255,.22);
        backdrop-filter: blur(6px);
        padding: 6px 14px; border-radius: 999px;
        font-size: .8rem; font-weight: 500;
        margin-bottom: 16px;
    }}
    .hero-chip .dot {{
        width: 8px; height: 8px; border-radius: 50%;
        background: #4ade80; box-shadow: 0 0 0 4px rgba(74,222,128,.25);
        animation: pulse 2s infinite;
    }}
    @keyframes pulse {{
        0%,100% {{ box-shadow: 0 0 0 4px rgba(74,222,128,.25); }}
        50%     {{ box-shadow: 0 0 0 8px rgba(74,222,128,.05); }}
    }}

    /* ---------- TABS ---------- */
    .nav-tabs-custom {{
        border-bottom: 1px solid var(--gray-200);
        gap: 4px;
        flex-wrap: nowrap;
        overflow-x: auto;
    }}
    .nav-tabs-custom::-webkit-scrollbar {{ display: none; }}
    .nav-tabs-custom .nav-link {{
        color: var(--gray-600);
        font-weight: 600;
        font-size: .92rem;
        border: none;
        background: transparent;
        padding: 14px 22px;
        border-radius: 10px 10px 0 0;
        position: relative;
        white-space: nowrap;
        transition: color .2s, background .2s;
    }}
    .nav-tabs-custom .nav-link:hover {{
        color: var(--primary);
        background: rgba(15,76,129,.05);
    }}
    .nav-tabs-custom .nav-link.active {{
        color: var(--primary);
        background: transparent;
    }}
    .nav-tabs-custom .nav-link.active::after {{
        content: "";
        position: absolute; left: 12px; right: 12px; bottom: -1px;
        height: 3px; border-radius: 3px 3px 0 0;
        background: linear-gradient(90deg, var(--primary), var(--accent));
    }}

    /* ---------- CARDS ---------- */
    .card-custom {{
        border: 1px solid var(--gray-200);
        border-radius: 16px;
        background: #fff;
        box-shadow: 0 1px 3px rgba(15,23,42,.04), 0 8px 24px rgba(15,23,42,.04);
        transition: box-shadow .3s ease, transform .3s ease;
        overflow: hidden;
    }}
    .card-custom:hover {{
        box-shadow: 0 4px 12px rgba(15,23,42,.06), 0 16px 40px rgba(15,23,42,.08);
    }}
    .card-header-custom {{
        background: #fff;
        border-bottom: 1px solid var(--gray-100);
        font-weight: 700;
        color: var(--gray-900);
        padding: 18px 22px;
        display: flex; align-items: center; justify-content: space-between;
        flex-wrap: wrap; gap: 10px;
    }}
    .section-eyebrow {{
        font-size: .7rem; font-weight: 700; letter-spacing: .12em;
        text-transform: uppercase; color: var(--accent);
        margin-bottom: 6px;
    }}

    /* ---------- MAP ---------- */
    .map-container {{
        min-height: 580px;
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid var(--gray-200);
        background: #fff;
    }}
    .legend {{
        display: flex; flex-wrap: wrap; gap: 14px;
        padding: 14px 18px;
        background: var(--gray-50);
        border: 1px solid var(--gray-200);
        border-radius: 12px;
        margin-bottom: 14px;
        font-size: .82rem;
    }}
    .legend-item {{ display: flex; align-items: center; gap: 8px; color: var(--gray-600); font-weight: 500; }}
    .legend-dot {{
        width: 12px; height: 12px; border-radius: 50%;
        box-shadow: 0 0 0 2px #fff, 0 0 0 3px currentColor;
    }}

    /* ---------- BADGES ---------- */
    .badge-soft {{
        display: inline-flex; align-items: center;
        padding: 5px 12px; border-radius: 999px;
        font-size: .75rem; font-weight: 600;
        white-space: nowrap;
    }}
    .badge-soft.success   {{ background: #d1fae5; color: #065f46; }}
    .badge-soft.warning   {{ background: #fef3c7; color: #92400e; }}
    .badge-soft.danger    {{ background: #fee2e2; color: #991b1b; }}
    .badge-soft.secondary {{ background: var(--gray-100); color: var(--gray-600); }}

    /* ---------- MODELS TABLE ---------- */
    .models-toolbar {{
        display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
        padding: 16px 22px;
        border-bottom: 1px solid var(--gray-100);
        background: #fff;
    }}
    .search-wrapper {{ position: relative; flex: 1 1 280px; min-width: 220px; }}
    .search-wrapper i {{
        position: absolute; left: 14px; top: 50%;
        transform: translateY(-50%);
        color: var(--gray-400); font-size: .9rem;
    }}
    .search-input {{
        width: 100%;
        padding: 10px 14px 10px 40px;
        border-radius: 10px;
        border: 1px solid var(--gray-200);
        background: var(--gray-50);
        font-size: .9rem;
        transition: border-color .2s, box-shadow .2s, background .2s;
    }}
    .search-input:focus {{
        outline: none;
        border-color: var(--primary-2);
        background: #fff;
        box-shadow: 0 0 0 4px rgba(30,111,191,.12);
    }}
    .models-table {{
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        font-size: .9rem;
    }}
    .models-table thead th {{
        background: var(--gray-50);
        color: var(--gray-600);
        font-size: .72rem;
        font-weight: 700;
        letter-spacing: .08em;
        text-transform: uppercase;
        padding: 14px 18px;
        border-bottom: 1px solid var(--gray-200);
        text-align: left;
        white-space: nowrap;
    }}
    .models-table tbody td {{
        padding: 16px 18px;
        border-bottom: 1px solid var(--gray-100);
        vertical-align: middle;
    }}
    .models-table tbody tr:last-child td {{ border-bottom: none; }}
    .models-table tbody tr {{ transition: background .15s; }}
    .models-table tbody tr:hover {{ background: var(--gray-50); }}
    .brand-avatar {{
        width: 34px; height: 34px; border-radius: 9px;
        display: inline-flex; align-items: center; justify-content: center;
        background: linear-gradient(135deg, var(--primary), var(--accent));
        color: #fff; font-weight: 700; font-size: .85rem;
        margin-right: 10px;
        box-shadow: 0 4px 10px rgba(15,76,129,.18);
    }}

    /* ---------- EMPTY STATE ---------- */
    .empty-state {{ padding: 40px 20px; text-align: center; color: var(--gray-600); }}
    .empty-state i {{ font-size: 3rem; color: var(--gray-400); opacity: .6; }}

    /* ---------- STATS ---------- */
    .stat-card {{
        background: #fff;
        border: 1px solid var(--gray-200);
        border-radius: 14px;
        padding: 18px 20px;
        display: flex; align-items: center; gap: 14px;
        transition: transform .25s, box-shadow .25s;
    }}
    .stat-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(15,23,42,.06);
    }}
    .stat-icon {{
        width: 46px; height: 46px; border-radius: 12px;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.15rem; color: #fff;
        background: linear-gradient(135deg, var(--primary), var(--primary-2));
        flex-shrink: 0;
    }}
    .stat-icon.accent  {{ background: linear-gradient(135deg, var(--accent), #48cae4); }}
    .stat-icon.purple  {{ background: linear-gradient(135deg, var(--purple), #a78bfa); }}
    .stat-value {{ font-size: 1.4rem; font-weight: 800; color: var(--gray-900); line-height: 1; }}
    .stat-label {{ font-size: .78rem; color: var(--gray-600); margin-top: 4px; }}

    /* ---------- METRO CARDS ---------- */
    .metro-card {{
        border: 1px solid var(--gray-200);
        border-radius: 14px;
        background: #fff;
        padding: 22px;
        height: 100%;
        transition: transform .25s, box-shadow .25s, border-color .25s;
    }}
    .metro-card:hover {{
        transform: translateY(-3px);
        border-color: var(--primary-2);
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

    /* ---------- INFO ---------- */
    .info-list {{ list-style: none; padding-left: 0; }}
    .info-list li {{
        padding-left: 28px; position: relative; margin-bottom: 10px;
        color: var(--gray-600); font-size: .93rem; line-height: 1.55;
    }}
    .info-list li::before {{
        content: "\\f00c";
        font-family: "Font Awesome 6 Free"; font-weight: 900;
        position: absolute; left: 0; top: 1px;
        color: var(--accent); font-size: .8rem;
    }}
    .type-card {{
        border-radius: 12px;
        padding: 16px 18px;
        border: 1px solid var(--gray-200);
        background: var(--gray-50);
        margin-bottom: 12px;
        transition: border-color .2s, background .2s;
    }}
    .type-card:hover {{ background: #fff; border-color: var(--primary-2); }}
    .type-card h6 {{ font-weight: 700; margin-bottom: 6px; color: var(--gray-900); }}
    .type-card p  {{ font-size: .84rem; color: var(--gray-600); margin: 0; }}

    @media (max-width: 576px) {{
        .hero-section {{ padding: 40px 0 32px; }}
        .nav-tabs-custom .nav-link {{ padding: 12px 14px; font-size: .82rem; }}
        .models-table thead {{ display: none; }}
        .models-table tbody td {{ display: block; padding: 10px 16px; border-bottom: 1px solid var(--gray-100); }}
        .models-table tbody tr {{ display: block; border-bottom: 2px solid var(--gray-100); padding: 6px 0; }}
    }}
</style>
</head>
<body>

<!-- HERO -->
<div class="hero-section">
    <div class="container hero-inner">
        <div class="row align-items-center">
            <div class="col-lg-8">
                <span class="hero-chip"><span class="dot"></span> Portal actualizado automáticamente</span>
                <h1 class="display-5 hero-title mb-2">
                    <i class="fa-solid fa-heart-pulse me-3"></i>Esfigmomanómetros
                </h1>
                <p class="lead hero-subtitle mb-0">
                    Portal informativo sobre equipos de medición de presión arterial en Uruguay:
                    registros habilitados, modelos aprobados y control metrológico legal.
                </p>
            </div>
            <div class="col-lg-4 text-lg-end mt-4 mt-lg-0 d-none d-lg-block">
                <i class="fa-solid fa-stethoscope" style="font-size: 6rem; opacity: .15;"></i>
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
                <i class="fa-solid fa-certificate me-2"></i>Modelos Aprobados
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

        <!-- ============ MAPA ============ -->
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
                    <div class="map-container">
                        {mapa_html_snippet}
                    </div>
                </div>
            </div>
        </div>

        <!-- ============ MODELOS APROBADOS ============ -->
        <div class="tab-pane fade" id="modelos-content" role="tabpanel">
            <div class="row g-3 mb-4">
                <div class="col-md-4">
                    <div class="stat-card">
                        <div class="stat-icon"><i class="fa-solid fa-list-check"></i></div>
                        <div>
                            <div class="stat-value">{total_modelos}</div>
                            <div class="stat-label">Modelos registrados</div>
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
                            <div class="stat-value">LATU</div>
                            <div class="stat-label">Autoridad de control</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card card-custom">
                <div class="card-header-custom">
                    <div>
                        <div class="section-eyebrow">Control metrológico</div>
                        <div><i class="fa-solid fa-certificate text-primary me-2"></i>Modelos de tensiómetros aprobados</div>
                    </div>
                </div>

                <div class="models-toolbar">
                    <div class="search-wrapper">
                        <i class="fa-solid fa-magnifying-glass"></i>
                        <input type="text" id="modelSearch" class="search-input" placeholder="Buscar por marca, modelo, tipo o resolución...">
                    </div>
                    <select id="typeFilter" class="form-select" style="max-width: 200px; border-radius: 10px; border-color: var(--gray-200);">
                        <option value="">Todos los tipos</option>
                        <option value="digital">Digital</option>
                        <option value="aneroide">Aneroide</option>
                        <option value="mercurio">Mercurio</option>
                    </select>
                </div>

                <div class="table-responsive">
                    <table class="models-table" id="modelsTable">
                        <thead>
                            <tr>
                                <th>Marca</th>
                                <th>Modelo</th>
                                <th>Tipo</th>
                                <th>Resolución</th>
                                <th>Fecha</th>
                                <th>Estado</th>
                            </tr>
                        </thead>
                        <tbody>
                            {modelos_rows_html}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- ============ INFO TÉCNICA ============ -->
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

        <!-- ============ METROLOGÍA ============ -->
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
    // Buscador + filtro de la tabla de modelos
    (function () {{
        const searchInput = document.getElementById('modelSearch');
        const typeFilter  = document.getElementById('typeFilter');
        const rows        = document.querySelectorAll('#modelsTable tbody tr');

        function filterRows() {{
            const term = (searchInput?.value || '').toLowerCase().trim();
            const type = (typeFilter?.value || '').toLowerCase();

            rows.forEach(row => {{
                if (row.querySelector('.empty-state')) return; // no tocar el estado vacío
                const text = row.textContent.toLowerCase();
                const matchesTerm = !term || text.includes(term);
                const matchesType = !type || text.includes(type);
                row.style.display = (matchesTerm && matchesType) ? '' : 'none';
            }});
        }}

        searchInput?.addEventListener('input', filterRows);
        typeFilter?.addEventListener('change', filterRows);
    }})();
</script>
</body>
</html>
"""

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(pag_web_completa)

print("✅ index.html generado correctamente.")
