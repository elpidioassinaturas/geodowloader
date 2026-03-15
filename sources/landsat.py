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

# Coleções STAC disponíveis
_COLLECTIONS = {
    "LANDSAT_9":    "landsat-c2l2-sr",
    "LANDSAT_8":    "landsat-c2l2-sr",
    "LANDSAT_9_ST": "landsat-c2l2-st",
    "LANDSAT_8_ST": "landsat-c2l2-st",
    "LANDSAT_9_L1": "landsat-c2l1",
    "LANDSAT_8_L1": "landsat-c2l1",
}

# Bandas principais para download (Surface Reflectance)
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
        aoi_wkt      : str   (WKT polygon, obrigatorio)
        product_type : str   (LANDSAT_8|LANDSAT_9|LANDSAT_8_ST|LANDSAT_9_ST|..._L1)
        start_date   : str   (YYYY-MM-DD)
        end_date     : str   (YYYY-MM-DD)
        cloud_cover  : int   (0-100)
        max_results  : int   (default 20)
    """
    try:
        from pystac_client import Client
    except ImportError:
        raise RuntimeError("Pacote 'pystac-client' nao instalado. Execute: pip install pystac-client")

    aoi = (params.get("aoi_wkt") or "").strip()
    if not aoi:
        raise ValueError("AOI e obrigatorio para busca de cenas Landsat.")

    mission     = params.get("product_type", "LANDSAT_9")
    start_date  = params.get("start_date", "2024-01-01")
    end_date    = params.get("end_date",   "2024-12-31")
    cloud_max   = int(params.get("cloud_cover", 30))
    max_results = int(params.get("max_results", 20))

    collection = _COLLECTIONS.get(mission, "landsat-c2l2-sr")
    platform   = _platform_filter(mission)
    bbox       = _wkt_to_bbox(aoi)

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

        # Thumbnail requer USGS ERS auth (diferente do NASA Earthdata)
        # Usa URL publica do visualizador LandsatLook para preview
        viewer_url = f"https://landsatlook.usgs.gov/stac-browser/collection02/./{it.id}"
        thumb = viewer_url   # abre no visualizador, nao carrega img direto

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

        # Tamanho estimado
        level = "L2-SR" if "sr" in collection else ("L2-ST" if "st" in collection else "L1")
        sat   = "9" if (it.id.startswith("LC09") or it.id.startswith("LE09")) else "8"

        items.append({
            "name":      it.id,
            "product":   f"Landsat {sat} C2-{level}",
            "date":      date,
            "cloud":     f"{cloud:.2f}%" if cloud is not None else "?",
            "size_mb":   round(len(all_urls) * 120.0, 0),  # ~120 MB/banda
            "url":       all_urls[0] if all_urls else "",
            "all_urls":  all_urls,
            "thumb":     thumb,
            "bbox":      None,
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
