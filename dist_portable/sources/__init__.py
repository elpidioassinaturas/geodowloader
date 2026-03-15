"""
sources/
========
Adaptadores de download para cada fonte de dados raster.

Cada módulo expõe:
    search(params: dict) -> list[dict]
    download(products: list, cfg: dict, log_fn: callable) -> None

Categorias e datasets disponíveis:
    Radar  : nisar, sentinel1, alos
    Optico : sentinel2, landsat
    MDE    : srtm (CopDEM GLO-30 via AWS S3), copdem
    Clima  : era5, chirps
"""

CATEGORIES = {
    "radar":  ["nisar", "sentinel1", "alos"],
    "optico": ["sentinel2", "landsat"],
    "mde":    ["srtm", "copdem"],
    "clima":  ["era5", "chirps"],
}

DATASET_LABELS = {
    "nisar":     {"label": "NISAR",          "icon": "🛰️",  "credential": "earthdata"},
    "sentinel1": {"label": "Sentinel-1",     "icon": "📡",  "credential": "copernicus"},
    "alos":      {"label": "ALOS/PALSAR",    "icon": "📡",  "credential": "earthdata"},
    "sentinel2": {"label": "Sentinel-2",     "icon": "🌿",  "credential": "copernicus"},
    "landsat":   {"label": "Landsat 8/9",    "icon": "🛰️", "credential": "earthdata"},
    "srtm":      {"label": "SRTM 30m",       "icon": "⛰️",  "credential": None},
    "copdem":    {"label": "Copernicus DEM", "icon": "🏔️",  "credential": "copernicus"},
    "era5":      {"label": "ERA5",           "icon": "🌧️", "credential": "cds"},
    "chirps":    {"label": "CHIRPS",         "icon": "🌧️", "credential": None},
}
