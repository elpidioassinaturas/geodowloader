#!/usr/bin/env python3
"""
sources/sentinel2.py
====================
Adapter Sentinel-2 — busca via CDSE OData, download OAuth2.
Credencial: Copernicus CDSE (email + password)
"""
from __future__ import annotations
from pathlib import Path
import requests

_ODATA_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
_TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"


def search(params: dict) -> list[dict]:
    """
    params esperados:
        product_type : str  (ex: "S2MSI2A", "S2MSI1C")
        start_date   : str
        end_date     : str
        max_results  : int
        aoi_wkt      : str
        cloud_cover  : int  (% máximo, ex: 30)
    """
    product_type = params.get("product_type", "S2MSI2A")
    start  = params.get("start_date", "")
    end    = params.get("end_date", "")
    limit  = int(params.get("max_results", 50))
    aoi    = (params.get("aoi_wkt") or "").strip()
    clouds = params.get("cloud_cover", 100)

    filters = [
        "Collection/Name eq 'SENTINEL-2'",
        f"Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' and att/OData.CSC.StringAttribute/Value eq '{product_type}')",
        f"Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' and att/OData.CSC.DoubleAttribute/Value le {clouds}.00)",
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
        raise RuntimeError(f"Erro na API CDSE Sentinel-2: {e}")

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


def _get_token(email: str, password: str) -> str:
    resp = requests.post(_TOKEN_URL, data={
        "client_id":  "cdse-public",
        "grant_type": "password",
        "username":   email,
        "password":   password,
    }, timeout=20)
    resp.raise_for_status()
    return resp.json()["access_token"]


def download(products: list[dict], cfg: dict, log_fn=print) -> None:
    cop      = cfg.get("copernicus", {})
    out_dir  = Path(cfg.get("download", {}).get("directory", "downloads/sentinel2"))
    out_dir.mkdir(parents=True, exist_ok=True)

    log_fn("Obtendo token Copernicus CDSE...")
    token   = _get_token(cop.get("email", ""), cop.get("password", ""))
    headers = {"Authorization": f"Bearer {token}"}

    log_fn(f"Iniciando download de {len(products)} produto(s)...")
    for i, prod in enumerate(products, 1):
        name = prod.get("name", f"produto_{i}")
        url  = prod.get("url", "")
        log_fn(f"[{i}/{len(products)}] Baixando: {name}")
        try:
            out_path = out_dir / f"{name}.zip"
            with requests.get(url, headers=headers, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        f.write(chunk)
            log_fn(f"  ✓ Concluído: {name}")
        except Exception as e:
            log_fn(f"  ✗ Erro em {name}: {e}")
