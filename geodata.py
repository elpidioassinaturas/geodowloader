#!/usr/bin/env python3
"""
geodata.py
==========
Funções de geocodificação e leitura de arquivos vetoriais para AOI.
Reaproveitado do projeto NISAR (elpidioassinaturas/nisar).
"""
from __future__ import annotations
import io
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import requests

# ── Países da América do Sul ──────────────────────────────────────────────────
SOUTH_AMERICA = {
    "Brasil":          "br",
    "Argentina":       "ar",
    "Chile":           "cl",
    "Peru":            "pe",
    "Colômbia":        "co",
    "Venezuela":       "ve",
    "Bolívia":         "bo",
    "Equador":         "ec",
    "Paraguai":        "py",
    "Uruguai":         "uy",
    "Guiana":          "gy",
    "Suriname":        "sr",
    "Guiana Francesa": "gf",
}

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_USER_AGENT    = "GeoDownloader/0.1.001 (geodownloader@github)"


def south_america_countries() -> list[dict]:
    """Retorna lista de {'name': str, 'code': str} dos países da América do Sul."""
    return [{"name": k, "code": v} for k, v in SOUTH_AMERICA.items()]


def geocode_area(
    country: str,
    state: str = "",
    municipality: str = "",
) -> dict:
    """
    Geocodifica uma área administrativa via Nominatim (OSM) e retorna WKT.

    Parâmetros
    ----------
    country      : nome do país (ex: "Brasil")
    state        : nome do estado/departamento (opcional)
    municipality : nome do município/cidade (opcional)

    Retorna
    -------
    {"wkt": str, "bbox": {W, E, S, N}, "display_name": str}
    ou {"error": str}
    """
    parts = [p for p in [municipality, state, country] if p.strip()]
    query = ", ".join(parts)
    country_code = SOUTH_AMERICA.get(country, "")

    params = {
        "q":              query,
        "format":         "json",
        "polygon_text":   1,
        "limit":          1,
        "accept-language": "pt-BR,pt;q=0.9",
    }
    if country_code:
        params["countrycodes"] = country_code

    try:
        resp = requests.get(
            _NOMINATIM_URL,
            params=params,
            headers={"User-Agent": _USER_AGENT},
            timeout=12,
        )
        resp.raise_for_status()
        results = resp.json()
    except requests.RequestException as e:
        return {"error": f"Erro na API Nominatim: {e}"}

    if not results:
        return {"error": f"Área não encontrada: {query}"}

    r = results[0]
    wkt_raw = r.get("geotext") or r.get("wkt") or ""

    if not wkt_raw and "boundingbox" in r:
        bb = r["boundingbox"]   # [S, N, W, E]
        s, n, w, e = float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])
        wkt_raw = f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))"

    if not wkt_raw:
        return {"error": "Nominatim não retornou geometria para esta área."}

    wkt = _simplify_wkt(wkt_raw)

    bb = r.get("boundingbox", [])
    if len(bb) == 4:
        bbox = {"S": round(float(bb[0]), 4), "N": round(float(bb[1]), 4),
                "W": round(float(bb[2]), 4), "E": round(float(bb[3]), 4)}
    else:
        bbox = _bbox_from_wkt(wkt)

    return {
        "wkt":          wkt,
        "bbox":         bbox,
        "display_name": r.get("display_name", query),
    }


def load_aoi_file(file_bytes: bytes, filename: str) -> dict:
    """
    Lê um shapefile (.zip) ou GeoPackage (.gpkg) e extrai WKT da AOI.

    Retorna
    -------
    {"wkt": str, "bbox": {W,E,S,N}, "n_features": int, "crs_original": str}
    ou {"error": str}
    """
    try:
        import geopandas as gpd
        from shapely.ops import unary_union
    except ImportError:
        return {"error": "geopandas não instalado. Execute: pip install geopandas>=0.14"}

    suffix = Path(filename).suffix.lower()

    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)

            if suffix == ".zip":
                with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                    z.extractall(tmp)
                shp_files = list(tmp.rglob("*.shp"))
                if not shp_files:
                    return {"error": "Nenhum arquivo .shp encontrado no .zip"}
                gdf = gpd.read_file(shp_files[0])

            elif suffix == ".gpkg":
                gpkg_path = tmp / filename
                gpkg_path.write_bytes(file_bytes)
                gdf = gpd.read_file(gpkg_path)

            else:
                return {"error": f"Formato não suportado: {suffix}. Use .zip (shapefile) ou .gpkg"}

            crs_original = str(gdf.crs) if gdf.crs else "desconhecido"
            n_features   = len(gdf)

            if gdf.crs and gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(epsg=4326)

            union  = unary_union(gdf.geometry)
            hull   = union.convex_hull
            wkt    = hull.wkt

            bounds = hull.bounds
            bbox = {
                "W": round(bounds[0], 4), "S": round(bounds[1], 4),
                "E": round(bounds[2], 4), "N": round(bounds[3], 4),
            }

            return {
                "wkt":          wkt,
                "bbox":         bbox,
                "n_features":   n_features,
                "crs_original": crs_original,
            }

    except Exception as e:
        return {"error": f"Erro ao ler arquivo: {e}"}


# ── Helpers internos ───────────────────────────────────────────────────────────
def _simplify_wkt(wkt: str, tolerance: float = 0.05) -> str:
    """Simplifica WKT complexo via shapely."""
    try:
        from shapely import wkt as swkt
        geom = swkt.loads(wkt)
        if geom.geom_type in ("Polygon", "MultiPolygon"):
            simplified = geom.simplify(tolerance, preserve_topology=True)
            from shapely.geometry import polygon as spoly
            if simplified.geom_type == "Polygon":
                simplified = spoly.orient(simplified, sign=1.0)
        else:
            simplified = geom.convex_hull
        return simplified.wkt
    except Exception:
        return wkt


def _bbox_from_wkt(wkt: str) -> dict:
    """Extrai bbox de um WKT."""
    try:
        from shapely import wkt as swkt
        b = swkt.loads(wkt).bounds
        return {"W": round(b[0], 4), "S": round(b[1], 4),
                "E": round(b[2], 4), "N": round(b[3], 4)}
    except Exception:
        return {}
