#!/usr/bin/env python3
"""
sources/landsat.py
==================
Adapter Landsat 8/9 — USGS LandsatLook STAC API (sem autenticação para busca).

STAC Server: https://landsatlook.usgs.gov/stac-server/
Coleções:
  landsat-c2l2-sr  — Collection 2 Level-2 Surface Reflectance (L8+L9)
  landsat-c2l2-st  — Collection 2 Level-2 Surface Temperature
  landsat-c2l1     — Collection 2 Level-1

Download: usa sessão autenticada NASA Earthdata via earthaccess
(as URLs de download do STAC requerem credenciais Earthdata/USGS)
"""
from __future__ import annotations
import os
import re
from pathlib import Path


_STAC_URL = "https://landsatlook.usgs.gov/stac-server/"

# Mapeamento correção → coleção STAC
_CORRECTION_COLLECTION = {
    "BOA":  "landsat-c2l2-sr",   # Bottom of Atmosphere (Surface Reflectance) — Level-2
    "TOA":  "landsat-c2l1",      # Top of Atmosphere (Level-1) — sem correção atmosférica
    "ST":   "landsat-c2l2-st",   # Surface Temperature — Level-2
}

# Bandas por tipo de produto
_SR_BANDS = ["coastal", "blue", "green", "red", "nir08", "swir16", "swir22", "qa_pixel"]
_ST_BANDS = ["lwir11", "qa_pixel", "qa_radsat"]
_L1_BANDS = ["coastal", "blue", "green", "red", "nir08", "swir16", "swir22", "panchromatic"]


def _wkt_to_bbox(wkt: str) -> list:
    """Extrai [W, S, E, N] de WKT POLYGON."""
    nums = list(map(float, re.findall(r"[-\d.]+",
        wkt.replace("POLYGON", "").replace("(", "").replace(")", ""))))
    lons = nums[0::2]
    lats = nums[1::2]
    return [min(lons), min(lats), max(lons), max(lats)]


def _platform_filter(mission: str) -> str | None:
    """Retorna prefixo do ID para filtrar por plataforma (L8 ou L9)."""
    if "8" in mission:
        return "LC08"
    if "9" in mission:
        return "LC09"
    return None


def search(params: dict) -> list[dict]:
    """
    Busca cenas Landsat via USGS LandsatLook STAC API.

    params esperados:
        aoi_wkt    : str   (WKT polygon, obrigatorio)
        satellite  : str   (Landsat 8 | Landsat 9 | Landsat 8+9)
        correction : str   (BOA | TOA | ST)
        start_date : str   (YYYY-MM-DD)
        end_date   : str   (YYYY-MM-DD)
        cloud_cover: int   (0-100)
        max_results: int   (default 20)
    """
    try:
        from pystac_client import Client
    except ImportError:
        raise RuntimeError("Pacote 'pystac-client' nao instalado. Execute: pip install pystac-client")

    aoi = (params.get("aoi_wkt") or "").strip()
    if not aoi:
        raise ValueError("AOI e obrigatorio para busca de cenas Landsat.")

    satellite   = params.get("satellite",  "Landsat 9")
    correction  = params.get("correction", "BOA")
    start_date  = params.get("start_date", "2024-01-01")
    end_date    = params.get("end_date",   "2024-12-31")
    cloud_max   = int(params.get("cloud_cover", 30))
    max_results = int(params.get("max_results", 20))

    # Mapeamento para coleção STAC
    collection = _CORRECTION_COLLECTION.get(correction, "landsat-c2l2-sr")

    # Prefixo do satélite para filtro pós-busca
    platform_map = {"Landsat 8": "LC08", "Landsat 9": "LC09"}
    platform = platform_map.get(satellite)   # None = sem filtro (8+9)

    bbox = _wkt_to_bbox(aoi)

    client = Client.open(_STAC_URL)

    # Filtro de cloud cover via query no STAC
    query = {}
    if cloud_max < 100:
        query["eo:cloud_cover"] = {"lte": cloud_max}

    search_kwargs = dict(
        collections=[collection],
        bbox=bbox,
        datetime=f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
        max_items=max_results * 2 if platform else max_results,
    )
    if query:
        search_kwargs["query"] = query

    result = client.search(**search_kwargs)
    stac_items = list(result.items())

    # Selects bands for download based on collection type
    if "st" in collection:
        band_keys = _ST_BANDS
    elif "l1" in collection:
        band_keys = _L1_BANDS
    else:
        band_keys = _SR_BANDS

    items = []
    for it in stac_items:
        # Filtra por plataforma (L8 x L9) se necessário
        if platform and not it.id.startswith(platform):
            continue

        cloud = it.properties.get("eo:cloud_cover", None)
        date  = it.datetime.strftime("%Y-%m-%d") if it.datetime else start_date

        # Constrói URL do thumbnail e do viewer a partir do scene ID
        # Formatos possíveis:
        #   LC08_L2SP_222076_20240531_... → wrs em parts[2]
        #   LC09TP_219075_20241126_...    → wrs em parts[1]
        base_id  = it.id.replace("_SR", "").replace("_ST", "").replace("_L1", "")
        parts_id = base_id.split("_")

        # Detecta índice do WRS (campo com 6 dígitos numéricos)
        wrs_idx = next(
            (i for i, p in enumerate(parts_id) if p.isdigit() and len(p) == 6),
            None
        )

        # level vem da coleção STAC (mais confiável que tentar ler do ID)
        if "l2" in collection or "sr" in collection or "st" in collection:
            level_path = "level-2"
        else:
            level_path = "level-1"

        if wrs_idx is not None and len(parts_id) > wrs_idx + 1:
            wrs    = parts_id[wrs_idx]
            path_s = wrs[:3]
            row_s  = wrs[3:6]
            # Data de aquisição vem do próximo campo (8 dígitos)
            date_field = next(
                (p for p in parts_id[wrs_idx+1:] if p.isdigit() and len(p) == 8),
                None
            )
            year_s = date_field[:4] if date_field else "2024"
            base_path = (
                f"https://landsatlook.usgs.gov/data/collection02/"
                f"{level_path}/standard/oli-tirs/{year_s}/{path_s}/{row_s}/{base_id}"
            )
            thumb      = f"{base_path}/{base_id}_thumb_small.jpeg"
            viewer_url = (
                f"https://landsatlook.usgs.gov/stac-browser/collection02/"
                f"{level_path}/standard/oli-tirs/{year_s}/{path_s}/{row_s}/{base_id}"
            )
        else:
            thumb      = None
            viewer_url = f"https://landsatlook.usgs.gov/stac-browser/collection02/{base_id}"

        # URLs de download das bandas (HTTPS direto)
        all_urls = []
        for key in band_keys:
            if key in it.assets:
                href = it.assets[key].href
                if href.startswith("https://"):
                    all_urls.append(href)

        # Adiciona MTL e QA
        for extra in ["MTL.json", "MTL.txt", "ANG.txt"]:
            if extra in it.assets:
                href = it.assets[extra].href
                if href.startswith("https://"):
                    all_urls.append(href)

        # Label do produto
        corr_label = {"BOA": "BOA (Sup. Reflectance)", "TOA": "TOA (Topo Atm.)", "ST": "Sup. Temperature"}
        sat = "9" if (it.id.startswith("LC09") or it.id.startswith("LE09")) else "8"
        product_label = f"Landsat {sat} — {corr_label.get(correction, correction)}"

        items.append({
            "name":       base_id,
            "product":    product_label,
            "date":       date,
            "cloud":      f"{cloud:.2f}%" if cloud is not None else "?",
            "size_mb":    round(len(all_urls) * 120.0, 0),
            "url":        all_urls[0] if all_urls else "",
            "all_urls":   all_urls,
            "thumb":      thumb,
            "viewer_url": viewer_url,
            "bbox":       None,
        })

        if len(items) >= max_results:
            break

    return items


def download(products: list[dict], cfg: dict, log_fn=print) -> None:
    """
    Baixa cenas Landsat via HTTPS autenticado (NASA Earthdata / USGS).

    products : lista com 'name', 'url', 'all_urls'
    cfg      : dict com 'earthdata' e 'download.directory'
    """
    earthdata = cfg.get("earthdata", {})
    user = earthdata.get("username", "")
    pwd  = earthdata.get("password", "")

    if not user or not pwd:
        raise RuntimeError("Credenciais NASA Earthdata nao configuradas. Acesse Configuracoes.")

    out_dir = Path(cfg.get("download", {}).get("directory", "downloads/landsat"))
    out_dir.mkdir(parents=True, exist_ok=True)

    # Autentica via earthaccess (gerencia redirect USGS/NASA)
    try:
        import earthaccess
        os.environ["EARTHDATA_USERNAME"] = user
        os.environ["EARTHDATA_PASSWORD"] = pwd
        earthaccess.login(strategy="environment")
        session = earthaccess.get_requests_https_session()
        log_fn(f"Autenticado como: {user} (earthaccess)")
    except Exception as e:
        import requests
        session = requests.Session()
        session.auth = (user, pwd)
        log_fn(f"Usando autenticacao basica: {user}")

    log_fn(f"Iniciando download de {len(products)} cena(s) Landsat...")

    for i, prod in enumerate(products, 1):
        name     = prod.get("name", f"cena_{i}")
        all_urls = prod.get("all_urls") or [prod.get("url", "")]
        log_fn(f"[{i}/{len(products)}] {name} — {len(all_urls)} banda(s)")

        scene_dir = out_dir / name
        scene_dir.mkdir(exist_ok=True)

        for url in all_urls:
            filename = url.split("/")[-1].split("?")[0] or "file"
            out_path = scene_dir / filename
            if out_path.exists():
                log_fn(f"  Ja existe: {filename}")
                continue
            try:
                with session.get(url, stream=True, timeout=180, allow_redirects=True) as r:
                    ct = r.headers.get("Content-Type", "")
                    if "text/html" in ct or r.status_code in (401, 403):
                        log_fn(f"  Erro de autenticacao ({r.status_code}) — {filename}")
                        break
                    r.raise_for_status()
                    total = 0
                    with open(out_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=2 * 1024 * 1024):
                            if chunk:
                                f.write(chunk)
                                total += len(chunk)
                log_fn(f"  OK: {filename} ({round(total/1e6, 1)} MB)")
            except Exception as e:
                log_fn(f"  Erro em {filename}: {e}")

        log_fn(f"  Cena salva em: {scene_dir}")
