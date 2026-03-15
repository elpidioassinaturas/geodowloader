#!/usr/bin/env python3
"""
sources/srtm.py
===============
Adapter SRTM 30m — download de tiles via NASA EarthData (LP DAAC).
Credencial: NASA Earthdata (username + password)

Tiles: SRTMGL1 (1 arc-second = ~30m)
URL base: https://e4ftl01.cr.usgs.gov/MEASURES/SRTMGL1.003/2000.02.11/
"""
from __future__ import annotations
import math
from pathlib import Path
import requests
from requests.auth import HTTPBasicAuth

_BASE_URL = "https://e4ftl01.cr.usgs.gov/MEASURES/SRTMGL1.003/2000.02.11"


def _wkt_to_bbox(wkt: str) -> dict:
    """Extrai bbox minx, miny, maxx, maxy de WKT simples."""
    import re
    nums = list(map(float, re.findall(r"[-\d.]+", wkt.replace("POLYGON", "").replace("(", "").replace(")", ""))))
    lons = nums[0::2]
    lats = nums[1::2]
    return {"W": min(lons), "E": max(lons), "S": min(lats), "N": max(lats)}


def _bbox_to_tiles(bbox: dict) -> list[str]:
    """Gera nomes de tiles SRTM que cobrem o bbox."""
    tiles = []
    for lat in range(int(math.floor(bbox["S"])), int(math.ceil(bbox["N"]))):
        for lon in range(int(math.floor(bbox["W"])), int(math.ceil(bbox["E"]))):
            ns = "N" if lat >= 0 else "S"
            ew = "E" if lon >= 0 else "W"
            tile = f"{ns}{abs(lat):02d}{ew}{abs(lon):03d}.SRTMGL1.hgt.zip"
            tiles.append(tile)
    return tiles


def search(params: dict) -> list[dict]:
    """
    Calcula tiles SRTM para o AOI e retorna lista de produtos.

    params esperados:
        aoi_wkt  : str  (WKT polygon)
    """
    aoi = (params.get("aoi_wkt") or "").strip()
    if not aoi:
        raise ValueError("AOI é obrigatório para busca de tiles SRTM")

    bbox  = _wkt_to_bbox(aoi)
    tiles = _bbox_to_tiles(bbox)

    items = []
    for tile in tiles:
        items.append({
            "name":    tile.replace(".SRTMGL1.hgt.zip", ""),
            "product": "SRTMGL1",
            "date":    "2000-02-11",
            "size_mb": 25.0,  # aproximado por tile
            "url":     f"{_BASE_URL}/{tile}",
            "tile":    tile,
            "thumb":   None,
            "bbox":    None,
        })
    return items


def download(products: list[dict], cfg: dict, log_fn=print) -> None:
    """
    Baixa tiles SRTM via Earthdata.

    products : lista de dicts com 'url', 'tile'
    cfg      : dict com 'earthdata' (username/password) e 'download.directory'
    """
    earthdata = cfg.get("earthdata", {})
    user = earthdata.get("username", "")
    pwd  = earthdata.get("password", "")

    out_dir = Path(cfg.get("download", {}).get("directory", "downloads/srtm"))
    out_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.auth = HTTPBasicAuth(user, pwd)
    session.headers.update({"User-Agent": "GeoDownloader/0.1.001"})

    log_fn(f"Iniciando download de {len(products)} tile(s) SRTM...")
    for i, prod in enumerate(products, 1):
        tile = prod.get("tile", prod.get("name", f"tile_{i}"))
        url  = prod.get("url", "")
        log_fn(f"[{i}/{len(products)}] Baixando tile: {tile}")
        try:
            out_path = out_dir / tile
            with session.get(url, stream=True, timeout=60, allow_redirects=True) as r:
                if r.status_code == 404:
                    log_fn(f"  ⚠ Tile não existe (oceano ou sem dados): {tile}")
                    continue
                r.raise_for_status()
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        f.write(chunk)
            log_fn(f"  ✓ Concluído: {tile}")
        except Exception as e:
            log_fn(f"  ✗ Erro em {tile}: {e}")
