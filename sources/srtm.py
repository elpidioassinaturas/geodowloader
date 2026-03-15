#!/usr/bin/env python3
"""
sources/srtm.py
===============
Adapter SRTM 30m — download de tiles via NASA EarthData (LP DAAC).
Credencial: NASA Earthdata (username + password)

Auth: NASA EarthData Login usa redirect OAuth para urs.earthdata.nasa.gov.
Implementação oficial: https://wiki.earthdata.nasa.gov/display/EL/How+To+Access+Data+With+Python
"""
from __future__ import annotations
import math
from pathlib import Path
import requests
import requests.utils


# ── Session oficial NASA EarthData ────────────────────────────────────────────
class EarthdataSession(requests.Session):
    """
    Session com suporte ao redirect OAuth da NASA EarthData Login.
    Padrão oficial: https://wiki.earthdata.nasa.gov/display/EL/How+To+Access+Data+With+Python
    
    Mantém Authorization APENAS para redirects que vão:
      - Para o host de autenticação (urs.earthdata.nasa.gov)
      - Para o mesmo host de origem (DAAC)
    Remove Authorization em outros domínios (ex: S3 buckets).
    """
    AUTH_HOST = 'urs.earthdata.nasa.gov'

    def rebuild_auth(self, prepared_request, response):
        if 'Authorization' in prepared_request.headers:
            original = requests.utils.urlparse(response.request.url)
            redirect = requests.utils.urlparse(prepared_request.url)
            # Remove auth apenas se for cross-domain E não for o host URS
            if (original.hostname != redirect.hostname and
                    redirect.hostname != self.AUTH_HOST and
                    original.hostname != self.AUTH_HOST):
                del prepared_request.headers['Authorization']
        return


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
    Baixa tiles SRTM via NASA Earthdata com suporte ao redirect OAuth.

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

    # auth como TUPLA — padrão oficial NASA (não HTTPBasicAuth)
    session = EarthdataSession()
    session.auth = (user, pwd)
    session.headers.update({"User-Agent": "GeoDownloader/0.1.013"})

    log_fn(f"Iniciando download de {len(products)} tile(s) SRTM...")
    log_fn(f"  Usuário Earthdata: {user}")

    for i, prod in enumerate(products, 1):
        tile = prod.get("tile", prod.get("name", f"tile_{i}"))
        url  = prod.get("url", "")
        log_fn(f"[{i}/{len(products)}] Baixando tile: {tile}")
        log_fn(f"  URL: {url}")
        try:
            out_path = out_dir / tile
            with session.get(url, stream=True, timeout=120, allow_redirects=True) as r:

                # Log do histórico de redirects — essencial para diagnóstico
                if r.history:
                    for redir in r.history:
                        log_fn(f"  → redirect {redir.status_code}: {redir.url}")
                    log_fn(f"  → final {r.status_code}: {r.url}")

                if r.status_code == 404:
                    log_fn(f"  ⚠ 404 — tile não encontrado no servidor.")
                    log_fn(f"    URL final: {r.url}")
                    continue
                if r.status_code in (401, 403):
                    log_fn(f"  ✗ Erro de autenticação ({r.status_code}) — verifique credenciais")
                    log_fn(f"    URL final: {r.url}")
                    break

                content_type = r.headers.get("Content-Type", "")
                if "text/html" in content_type:
                    log_fn(f"  ✗ Recebeu HTML em vez do arquivo — autenticação falhou")
                    log_fn(f"    URL final: {r.url}")
                    log_fn(f"    Content-Type: {content_type}")
                    break

                r.raise_for_status()
                total = 0
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            total += len(chunk)
                log_fn(f"  ✓ Concluído: {tile} ({round(total/1e6,1)} MB → {out_path})")

        except Exception as e:
            log_fn(f"  ✗ Erro em {tile}: {e}")


