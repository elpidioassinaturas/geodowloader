#!/usr/bin/env python3
"""
sources/sentinel2.py
====================
Adapter Sentinel-2 — busca via Copernicus Data Space Ecosystem (CDSE).
Credencial: Copernicus CDSE (email + password)

Produtos:
  S2MSI2A — Level-2A (reflectância de superfície, BOA) — recomendado
  S2MSI1C — Level-1C (reflectância topo-de-atmosfera, TOA)

API de busca  : OData REST (sem autenticação)
API de download: OAuth2 token CDSE
Thumbnails    : quicklook público via CDSE OData
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable

import requests

_ODATA_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
_TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
_QUICK_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products({id})/Quicklook"


# ── Search ────────────────────────────────────────────────────────────────────
def search(params: dict) -> list[dict]:
    """
    params esperados:
        product_type : str  ("S2MSI2A" ou "S2MSI1C")
        start_date   : str  ("2025-01-01")
        end_date     : str  ("2025-12-31")
        cloud_cover  : int  (% máximo, default 30)
        max_results  : int
        wkt / aoi_wkt: str  (WKT polygon)
    """
    product_type = params.get("product_type", "S2MSI2A")
    start        = params.get("start_date", "")
    end          = params.get("end_date", "")
    cloud_max    = int(params.get("cloud_cover", 30))
    limit        = int(params.get("max_results", 50))
    aoi          = (params.get("wkt") or params.get("aoi_wkt") or "").strip()

    filters = [
        "Collection/Name eq 'SENTINEL-2'",
        (
            f"Attributes/OData.CSC.StringAttribute/any("
            f"att:att/Name eq 'productType' and "
            f"att/OData.CSC.StringAttribute/Value eq '{product_type}')"
        ),
        (
            f"Attributes/OData.CSC.DoubleAttribute/any("
            f"att:att/Name eq 'cloudCover' and "
            f"att/OData.CSC.DoubleAttribute/Value le {cloud_max:.1f})"
        ),
    ]
    if start:
        filters.append(f"ContentDate/Start gt {start}T00:00:00.000Z")
    if end:
        filters.append(f"ContentDate/Start lt {end}T23:59:59.000Z")
    if aoi:
        filters.append(f"OData.CSC.Intersects(area=geography'SRID=4326;{aoi}')")

    query = {
        "$filter":  " and ".join(filters),
        "$top":     limit,
        "$orderby": "ContentDate/Start desc",
        "$expand":  "Attributes",   # necessário para ler cloudCover
    }

    try:
        resp = requests.get(_ODATA_URL, params=query, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Erro na API CDSE Sentinel-2: {e}")

    items = []
    for p in data.get("value", []):
        prod_id  = p.get("Id", "")
        size_mb  = round((p.get("ContentLength") or 0) / 1e6, 1)
        date_str = (p.get("ContentDate") or {}).get("Start", "")[:10]

        # Extrai cloud cover dos atributos expandidos
        cloud = None
        for attr in (p.get("Attributes") or []):
            if attr.get("Name") == "cloudCover":
                try:
                    cloud = f"{float(attr['Value']):.1f}%"
                except Exception:
                    pass

        thumb = _QUICK_URL.format(id=prod_id) if prod_id else None

        items.append({
            "name":    p.get("Name", ""),
            "product": product_type,
            "date":    date_str,
            "cloud":   cloud or "?",
            "size_mb": size_mb,
            "url":     f"https://zipper.dataspace.copernicus.eu/odata/v1/Products({prod_id})/$value",
            "id":      prod_id,
            "thumb":   thumb,
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
def download(products: list[dict], cfg: dict, log_fn: Callable[[str], None] = print) -> None:
    cop      = cfg.get("copernicus", {})
    email    = cop.get("email", "")
    password = cop.get("password", "")

    if not email or not password:
        raise RuntimeError(
            "Credenciais Copernicus não configuradas. "
            "Acesse ⚙️ Configurações e preencha email/senha CDSE."
        )

    out_dir = Path(cfg.get("download", {}).get("directory", "downloads")) / "sentinel2"
    out_dir.mkdir(parents=True, exist_ok=True)

    log_fn("Obtendo token Copernicus CDSE...")
    try:
        token = _get_token(email, password)
    except Exception as e:
        raise RuntimeError(f"Falha na autenticação CDSE: {e}")

    headers = {"Authorization": f"Bearer {token}"}
    log_fn(f"Iniciando download de {len(products)} produto(s)...")

    for i, prod in enumerate(products, 1):
        name     = prod.get("name", f"produto_{i}")
        url      = prod.get("url", "")
        out_path = out_dir / f"{name}.zip"

        if out_path.exists():
            log_fn(f"  ↷ Já existe: {name}.zip")
            log_fn(f"  ✓ {name}")
            continue

        log_fn(f"[{i}/{len(products)}] Baixando: {name}")
        tmp = out_path.with_suffix(".tmp")
        try:
            with requests.get(url, headers=headers, stream=True, timeout=120) as r:
                r.raise_for_status()
                downloaded = 0
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        f.write(chunk)
                        downloaded += len(chunk)
            os.replace(tmp, out_path)
            size_mb = round(downloaded / 1e6, 1)
            log_fn(f"  ✓ {name} ({size_mb} MB)")
        except Exception as e:
            log_fn(f"  ✗ Erro em {name}: {e}")
            if tmp.exists():
                tmp.unlink(missing_ok=True)

        time.sleep(0.5)  # cortesia CDSE (max 2 simultâneos por conta)
