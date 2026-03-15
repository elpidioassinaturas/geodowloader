#!/usr/bin/env python3
"""
sources/srtm.py
===============
Adapter DEM 30m — Copernicus DEM GLO-30 via AWS S3 (Open Data, sem autenticação).

O Copernicus DEM GLO-30 é derivado do TanDEM-X (DLR/ESA) com qualidade
superior ao SRTM original. Tiles 1°x1°, resolução ~30m, cobertura global.

Fonte: AWS Open Data Registry
  s3://copernicus-dem-30m/
  https://copernicus-dem-30m.s3.amazonaws.com/

Não requer autenticação — acesso público gratuito.
"""
from __future__ import annotations
import math
from pathlib import Path
import requests

_S3_BASE = "https://copernicus-dem-30m.s3.amazonaws.com"


def _tile_name(lat: int, lon: int) -> str:
    """Gera nome do tile CopDEM GLO-30.
    Exemplo: lat=-22, lon=-45  ->  Copernicus_DSM_COG_10_S22_00_W045_00_DEM
    """
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"Copernicus_DSM_COG_10_{ns}{abs(lat):02d}_00_{ew}{abs(lon):03d}_00_DEM"


def _wkt_to_bbox(wkt: str) -> dict:
    """Extrai bbox (W, E, S, N) de WKT POLYGON."""
    import re
    nums = list(map(float, re.findall(r"[-\d.]+",
        wkt.replace("POLYGON", "").replace("(", "").replace(")", ""))))
    lons = nums[0::2]
    lats = nums[1::2]
    return {"W": min(lons), "E": max(lons), "S": min(lats), "N": max(lats)}


def _bbox_to_tiles(bbox: dict) -> list[tuple]:
    """Gera lista de (lat, lon) dos tiles que cobrem o bbox."""
    tiles = []
    for lat in range(int(math.floor(bbox["S"])), int(math.ceil(bbox["N"]))):
        for lon in range(int(math.floor(bbox["W"])), int(math.ceil(bbox["E"]))):
            tiles.append((lat, lon))
    return tiles


def search(params: dict) -> list[dict]:
    """
    Calcula tiles CopDEM GLO-30 para o AOI e retorna lista de produtos.

    params esperados:
        aoi_wkt : str  (WKT polygon, obrigatório)
    """
    aoi = (params.get("aoi_wkt") or "").strip()
    if not aoi:
        raise ValueError("AOI e obrigatorio para busca de tiles DEM. Selecione uma area no mapa.")

    bbox  = _wkt_to_bbox(aoi)
    tiles = _bbox_to_tiles(bbox)

    items = []
    for lat, lon in tiles:
        name = _tile_name(lat, lon)
        url  = f"{_S3_BASE}/{name}/{name}.tif"
        items.append({
            "name":    name,
            "product": "SRTM 30m",
            "date":    "2000-02-11",
            "size_mb": 50.0,
            "url":     url,
            "tile":    name,
            "lat":     lat,
            "lon":     lon,
            "thumb":   None,
            "bbox": {
                "minLat": lat,   "maxLat": lat + 1,
                "minLon": lon,   "maxLon": lon + 1,
            },
        })
    return items


def download(products: list[dict], cfg: dict, log_fn=print) -> None:
    """
    Baixa tiles Copernicus DEM GLO-30 do AWS S3 publico (sem autenticacao).

    products : lista de dicts com 'url', 'tile'
    cfg      : dict com 'download.directory'
    """
    out_dir = Path(cfg.get("download", {}).get("directory", "downloads/srtm"))
    out_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": "GeoDownloader/0.1.014"})

    log_fn(f"Iniciando download de {len(products)} tile(s) Copernicus DEM GLO-30...")
    log_fn(f"  Fonte: AWS S3 Open Data (sem autenticacao requerida)")

    for i, prod in enumerate(products, 1):
        tile = prod.get("tile", prod.get("name", f"tile_{i}"))
        url  = prod.get("url", "")
        log_fn(f"[{i}/{len(products)}] Baixando: {tile}")
        log_fn(f"  URL: {url}")

        try:
            out_path = out_dir / f"{tile}.tif"
            with session.get(url, stream=True, timeout=120) as r:
                if r.status_code == 404:
                    log_fn(f"  ⚠ Tile nao disponivel (oceano ou area sem dados): {tile}")
                    continue
                r.raise_for_status()
                total = 0
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            total += len(chunk)
            log_fn(f"  ✓ Concluido: {tile}.tif ({round(total/1e6, 1)} MB)")
        except Exception as e:
            log_fn(f"  ✗ Erro em {tile}: {e}")
