#!/usr/bin/env python3
"""
sources/srtm.py
===============
Adapter SRTM 30m — download de tiles via NASA EarthData (LP DAAC).
Credencial: NASA Earthdata (username + password)

Tiles: SRTMGL1 (1 arc-second = ~30m)
URL base: https://e4ftl01.cr.usgs.gov/MEASURES/SRTMGL1.003/2000.02.11/

NOTA DE AUTENTICAÇÃO:
  A NASA Earthdata usa redirect OAuth para urs.earthdata.nasa.gov.
  O HTTPBasicAuth simples não repassa credenciais no redirect.
  EarthdataSession sobrescreve rebuild_auth para lidar com isso.
"""
from __future__ import annotations
import math
from pathlib import Path
import requests
from requests.auth import HTTPBasicAuth


# ── Session com suporte ao redirect OAuth da NASA ─────────────────────────────
class EarthdataSession(requests.Session):
    """Session que repassa credenciais ao redirecionar para urs.earthdata.nasa.gov."""

    def rebuild_auth(self, prepared_request, response):
        """Mantém auth nos redirects dentro do domínio NASA."""
        hostname = prepared_request.url.split("//")[-1].split("/")[0].lower()
        if "earthdata.nasa.gov" in hostname or "e4ftl01.cr.usgs.gov" in hostname:
            prepared_request.prepare_auth(self.auth, prepared_request.url)
        else:
            # Remove auth para domínios externos (segurança)
            prepared_request.headers.pop("Authorization", None)


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
    Baixa tiles SRTM via Earthdata com suporte ao redirect OAuth da NASA.

    products : lista de dicts com 'url', 'tile'
    cfg      : dict com 'earthdata' (username/password) e 'download.directory'
    """
    earthdata = cfg.get("earthdata", {})
    user = earthdata.get("username", "")
    pwd  = earthdata.get("password", "")

    if not user or not pwd:
        raise RuntimeError("Credenciais NASA Earthdata não configuradas. Acesse ⚙️ Configurações.")

    out_dir = Path(cfg.get("download", {}).get("directory", "downloads/srtm"))
    out_dir.mkdir(parents=True, exist_ok=True)

    # Usa EarthdataSession que repassa as credenciais no redirect OAuth
    session = EarthdataSession()
    session.auth = HTTPBasicAuth(user, pwd)
    session.headers.update({"User-Agent": "GeoDownloader/0.1.011"})

    log_fn(f"Iniciando download de {len(products)} tile(s) SRTM...")
    log_fn(f"  Usuário Earthdata: {user}")

    for i, prod in enumerate(products, 1):
        tile = prod.get("tile", prod.get("name", f"tile_{i}"))
        url  = prod.get("url", "")
        log_fn(f"[{i}/{len(products)}] Baixando tile: {tile}")
        try:
            out_path = out_dir / tile
            with session.get(url, stream=True, timeout=120, allow_redirects=True) as r:
                if r.status_code == 404:
                    log_fn(f"  ⚠ Tile não existe no servidor (oceano ou sem cobertura): {tile}")
                    continue
                if r.status_code in (401, 403):
                    log_fn(f"  ✗ Erro de autenticação ({r.status_code}) — verifique suas credenciais NASA Earthdata")
                    log_fn(f"    URL redirecionada: {r.url}")
                    break
                # Detecta se recebeu HTML da página de login em vez do arquivo
                content_type = r.headers.get("Content-Type", "")
                if "text/html" in content_type:
                    log_fn(f"  ✗ Recebeu página HTML em vez do arquivo — autenticação falhou")
                    log_fn(f"    URL: {r.url}")
                    log_fn(f"    Verifique usuário/senha em ⚙️ Configurações")
                    break
                r.raise_for_status()
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
            log_fn(f"  ✓ Concluído: {tile} → {out_path}")
        except Exception as e:
            log_fn(f"  ✗ Erro em {tile}: {e}")

