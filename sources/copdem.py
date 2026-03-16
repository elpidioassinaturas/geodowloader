"""
sources/copdem.py — Copernicus DEM (GLO-30 / GLO-90)
=====================================================
Dados públicos no AWS S3 — sem autenticação necessária.

Bucket GLO-30: s3://copernicus-dem-30m  (acesso HTTP público)
Bucket GLO-90: s3://copernicus-dem-90m

Tiles 1°x1°, nomeados pelo canto SW:
  Copernicus_DSM_COG_10_N{lat:02d}_00_{EW}{lon:03d}_00_DEM.tif  (GLO-30)
  Copernicus_DSM_COG_30_N{lat:02d}_00_{EW}{lon:03d}_00_DEM.tif  (GLO-90)
"""
from __future__ import annotations

import math
import os
import re
import time
from pathlib import Path
from typing import Callable

import requests

# ── URLs base ─────────────────────────────────────────────────────────────────
_BASE = {
    "GLO-30": "https://copernicus-dem-30m.s3.amazonaws.com",
    "GLO-90": "https://copernicus-dem-90m.s3.amazonaws.com",
}
_PREFIX = {
    "GLO-30": "Copernicus_DSM_COG_10",
    "GLO-90": "Copernicus_DSM_COG_30",
}


def _tile_url(base: str, prefix: str, lat: int, lon: int) -> str:
    """Constrói a URL de um tile 1°x1° pelo canto SW (lat/lon inteiro)."""
    ns   = "N" if lat >= 0 else "S"
    ew   = "E" if lon >= 0 else "W"
    alat = abs(lat)
    alon = abs(lon)
    name = f"{prefix}_{ns}{alat:02d}_00_{ew}{alon:03d}_00_DEM"
    return f"{base}/{name}/{name}.tif"


def _bbox_from_wkt(wkt: str) -> tuple[float, float, float, float]:
    """Extrai bbox (minlon, minlat, maxlon, maxlat) de um WKT POLYGON."""
    nums = re.findall(r"[-\d.]+", wkt)
    coords = [(float(nums[i]), float(nums[i + 1])) for i in range(0, len(nums) - 1, 2)]
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return min(lons), min(lats), max(lons), max(lats)


def _tiles_for_bbox(minlon, minlat, maxlon, maxlat) -> list[tuple[int, int]]:
    """Retorna lista de cantos SW (lat_int, lon_int) que cobrem a bbox."""
    tiles = []
    for lat in range(math.floor(minlat), math.ceil(maxlat)):
        for lon in range(math.floor(minlon), math.ceil(maxlon)):
            tiles.append((lat, lon))
    return tiles


# ── search ────────────────────────────────────────────────────────────────────
def search(params: dict) -> list[dict]:
    wkt        = (params.get("aoi_wkt") or params.get("wkt") or "").strip()
    resolution = params.get("resolution", "GLO-30")

    if resolution not in _BASE:
        resolution = "GLO-30"

    base   = _BASE[resolution]
    prefix = _PREFIX[resolution]

    if not wkt:
        return [{"error": "AOI não definida. Defina a área de interesse antes de buscar."}]

    try:
        minlon, minlat, maxlon, maxlat = _bbox_from_wkt(wkt)
    except Exception:
        return [{"error": "AOI inválida. Desenhe um polígono ou retângulo no mapa."}]

    tile_coords = _tiles_for_bbox(minlon, minlat, maxlon, maxlat)
    if len(tile_coords) > 100:
        return [{"error": f"AOI muito grande: {len(tile_coords)} tiles. Reduza a área de interesse."}]

    items = []
    sess  = requests.Session()
    sess.headers["User-Agent"] = "GeoDownloader/1.0"

    for lat, lon in tile_coords:
        url  = _tile_url(base, prefix, lat, lon)
        name = url.split("/")[-1]

        # Verifica disponibilidade com HEAD (rápido, sem baixar)
        try:
            r = sess.head(url, timeout=10, allow_redirects=True)
            if r.status_code == 404:
                continue          # tile não existe (oceano/área sem dado)
            size_mb = round(int(r.headers.get("Content-Length", 0)) / (1024 * 1024), 1)
        except requests.RequestException:
            size_mb = 0.0

        items.append({
            "name":     name,
            "product":  resolution,
            "date":     "—",
            "cloud":    "—",
            "size_mb":  size_mb,
            "thumb":    None,
            "url":      url,
        })

    if not items:
        return [{"error": "Nenhum tile encontrado para esta AOI (pode ser área oceânica)."}]

    return items


# ── download ──────────────────────────────────────────────────────────────────
def download(products: list[dict], cfg: dict, log_fn: Callable[[str], None]) -> None:
    out_dir = Path(cfg.get("download", {}).get("directory", "downloads")) / "copdem"
    out_dir.mkdir(parents=True, exist_ok=True)

    sess = requests.Session()
    sess.headers["User-Agent"] = "GeoDownloader/1.0"

    for p in products:
        url  = p.get("url", "")
        name = p.get("name", url.split("/")[-1])
        dest = out_dir / name

        if dest.exists():
            log_fn(f"  ↷ Já existe: {name}")
            log_fn(f"  ✓ {name}")
            continue

        log_fn(f"  ⬇ Baixando: {name}")
        try:
            r = sess.get(url, stream=True, timeout=60)
            r.raise_for_status()
            total = int(r.headers.get("Content-Length", 0))
            downloaded = 0
            tmp = dest.with_suffix(".tmp")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    f.write(chunk)
                    downloaded += len(chunk)
            os.replace(tmp, dest)
            size_mb = round(downloaded / (1024 * 1024), 1)
            log_fn(f"  ✓ {name} ({size_mb} MB)")
        except Exception as e:
            log_fn(f"  ✗ Erro em {name}: {e}")
            if dest.with_suffix(".tmp").exists():
                dest.with_suffix(".tmp").unlink(missing_ok=True)

        time.sleep(0.2)  # cortesia com o S3
