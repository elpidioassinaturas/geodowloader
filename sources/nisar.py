#!/usr/bin/env python3
"""
sources/nisar.py
================
Adapter NISAR — busca e download via ASF DAAC (asf_search).
Credencial: NASA Earthdata (username + password)
"""
from __future__ import annotations
from pathlib import Path

try:
    import asf_search as asf
    ASF_AVAILABLE = True
except ImportError:
    asf = None
    ASF_AVAILABLE = False


# ── Search ────────────────────────────────────────────────────────────────────
def search(params: dict) -> list[dict]:
    """
    Busca produtos NISAR no ASF DAAC.

    params esperados:
        product_type : str  (ex: "GCOV")
        start_date   : str  (ex: "2025-10-17")
        end_date     : str  (ex: "2026-01-20")
        max_results  : int
        aoi_wkt      : str  (WKT polygon, opcional)
    """
    if not ASF_AVAILABLE:
        raise RuntimeError("asf_search não instalado. Execute: pip install asf_search")

    kwargs = dict(
        platform=[asf.PLATFORM.NISAR],
        processingLevel=params.get("product_type", "GCOV"),
        start=params.get("start_date"),
        end=params.get("end_date"),
        maxResults=int(params.get("max_results", 50)),
    )
    aoi = (params.get("aoi_wkt") or "").strip()
    if aoi:
        kwargs["intersectsWith"] = aoi

    results = asf.search(**kwargs)
    items = []
    for r in results:
        p = r.properties

        raw_bytes = p.get("bytes", None)
        if isinstance(raw_bytes, dict):
            total_bytes = sum(
                v.get("bytes", 0) if isinstance(v, dict) else (v or 0)
                for v in raw_bytes.values()
            )
        elif isinstance(raw_bytes, (int, float)):
            total_bytes = raw_bytes
        else:
            total_bytes = 0
        try:
            size_mb = round(float(total_bytes) / 1e6, 1)
        except (TypeError, ValueError):
            size_mb = 0

        browse_urls = p.get("browse") or []
        thumb = browse_urls[0] if browse_urls else None

        bbox = None
        utm_zone = None
        try:
            coords = r.geometry["coordinates"][0]
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            min_lon, max_lon = min(lons), max(lons)
            min_lat, max_lat = min(lats), max(lats)
            bbox = {
                "minLon": round(min_lon, 2), "maxLon": round(max_lon, 2),
                "minLat": round(min_lat, 2), "maxLat": round(max_lat, 2),
            }
            center_lon = (min_lon + max_lon) / 2
            center_lat = (min_lat + max_lat) / 2
            zone_num = int((center_lon + 180) / 6) + 1
            hemi = "N" if center_lat >= 0 else "S"
            epsg = 32600 + zone_num if hemi == "N" else 32700 + zone_num
            utm_zone = {"zone": f"{zone_num}{hemi}", "epsg": epsg}
        except Exception:
            pass

        items.append({
            "name":      str(p.get("sceneName") or ""),
            "product":   str(p.get("processingLevel") or ""),
            "date":      str(p.get("startTime") or ""),
            "size_mb":   size_mb,
            "url":       str(p.get("url") or ""),
            "thumb":     thumb,
            "direction": str(p.get("flightDirection") or ""),
            "orbit":     p.get("orbit"),
            "utm_zone":  utm_zone,
            "bbox":      bbox,
        })
    return items


# ── Download ──────────────────────────────────────────────────────────────────
def download(products: list[dict], cfg: dict, log_fn=print) -> None:
    """
    Baixa produtos NISAR selecionados.

    products : lista de dicts com chave "name" (sceneName)
    cfg      : dict com 'earthdata' (username/password) e 'download.directory'
    log_fn   : callable para logging em tempo real
    """
    if not ASF_AVAILABLE:
        raise RuntimeError("asf_search não instalado.")

    earthdata = cfg.get("earthdata", {})
    session = asf.ASFSession().auth_with_creds(earthdata["username"], earthdata["password"])

    out_dir = cfg.get("download", {}).get("directory", "downloads/nisar")
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    names = [r["name"] for r in products]
    asf_products = asf.granule_search(names)

    log_fn(f"Iniciando download de {len(asf_products)} produto(s)...")
    for i, product in enumerate(asf_products, 1):
        name = product.properties.get("sceneName", f"produto_{i}")
        log_fn(f"[{i}/{len(asf_products)}] Baixando: {name}")
        try:
            product.download(path=out_dir, session=session)
            log_fn(f"  ✓ Concluído: {name}")
        except Exception as e:
            log_fn(f"  ✗ Erro em {name}: {e}")
