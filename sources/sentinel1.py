#!/usr/bin/env python3
"""
sources/sentinel1.py
====================
Adapter Sentinel-1 — busca via Copernicus Data Space Ecosystem (CDSE).
Credencial: Copernicus (email + password)

API de busca: OData REST (sem autenticação)
API de download: OAuth2 token CDSE
"""
from __future__ import annotations
from pathlib import Path
import requests

_ODATA_URL   = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
_TOKEN_URL   = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"


# ── Search ────────────────────────────────────────────────────────────────────
def search(params: dict) -> list[dict]:
    """
    Busca produtos Sentinel-1 no CDSE OData.

    params esperados:
        product_type : str  (ex: "GRD", "SLC", "RAW")
        start_date   : str  (ex: "2025-01-01")
        end_date     : str  (ex: "2025-03-31")
        max_results  : int
        aoi_wkt      : str  (WKT polygon, opcional)
    """
    product_type = params.get("product_type", "GRD")
    start = params.get("start_date", "")
    end   = params.get("end_date", "")
    limit = int(params.get("max_results", 50))
    aoi   = (params.get("aoi_wkt") or "").strip()

    filters = [
        "Collection/Name eq 'SENTINEL-1'",
        f"Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' and att/OData.CSC.StringAttribute/Value eq '{product_type}')",
    ]
    if start:
        filters.append(f"ContentDate/Start gt {start}T00:00:00.000Z")
    if end:
        filters.append(f"ContentDate/Start lt {end}T23:59:59.000Z")
    if aoi:
        filters.append(f"OData.CSC.Intersects(area=geography'SRID=4326;{aoi}')")

    query = {
        "$filter": " and ".join(filters),
        "$top":    limit,
        "$orderby": "ContentDate/Start desc",
    }

    try:
        resp = requests.get(_ODATA_URL, params=query, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Erro na API CDSE: {e}")

    items = []
    for p in data.get("value", []):
        size_mb = round((p.get("ContentLength") or 0) / 1e6, 1)
        items.append({
            "name":    p.get("Name", ""),
            "product": product_type,
            "date":    (p.get("ContentDate") or {}).get("Start", ""),
            "size_mb": size_mb,
            "url":     f"https://zipper.dataspace.copernicus.eu/odata/v1/Products({p.get('Id')})/$value",
            "id":      p.get("Id", ""),
            "thumb":   None,
            "bbox":    None,
        })
    return items


# ── Token OAuth2 ──────────────────────────────────────────────────────────────
def _get_token(email: str, password: str) -> str:
    resp = requests.post(_TOKEN_URL, data={
        "client_id":  "cdse-public",
        "grant_type": "password",
        "username":   email,
        "password":   password,
    }, timeout=20)
    resp.raise_for_status()
    return resp.json()["access_token"]


# ── Download ──────────────────────────────────────────────────────────────────
def download(products: list[dict], cfg: dict, log_fn=print) -> None:
    """
    Baixa produtos Sentinel-1 do CDSE.

    products : lista de dicts com 'url', 'name', 'id'
    cfg      : dict com 'copernicus' (email/password) e 'download.directory'
    log_fn   : callable de log
    """
    cop = cfg.get("copernicus", {})
    email    = cop.get("email", "")
    password = cop.get("password", "")

    out_dir = Path(cfg.get("download", {}).get("directory", "downloads/sentinel1"))
    out_dir.mkdir(parents=True, exist_ok=True)

    log_fn("Obtendo token Copernicus CDSE...")
    try:
        token = _get_token(email, password)
    except Exception as e:
        raise RuntimeError(f"Falha na autenticação CDSE: {e}")

    headers = {"Authorization": f"Bearer {token}"}
    log_fn(f"Iniciando download de {len(products)} produto(s)...")

    for i, prod in enumerate(products, 1):
        name = prod.get("name", f"produto_{i}")
        url  = prod.get("url", "")
        log_fn(f"[{i}/{len(products)}] Baixando: {name}")
        try:
            out_path = out_dir / f"{name}.zip"
            with requests.get(url, headers=headers, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        f.write(chunk)
            log_fn(f"  ✓ Concluído: {name}")
        except Exception as e:
            log_fn(f"  ✗ Erro em {name}: {e}")
