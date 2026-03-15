#!/usr/bin/env python3
"""
sources/srtm.py
===============
Adapter SRTM 30m — NASA Earthdata via earthaccess (abordagem oficial LP DAAC).
Credencial: NASA Earthdata (username + password)

Fluxo:
  1. search(): autentica com earthaccess, busca via CMR, extrai URLs HTTPS reais
  2. download(): usa sessao autenticada earthaccess para baixar pelas URLs extraidas
"""
from __future__ import annotations
import os
import re
from pathlib import Path


def _wkt_to_bbox(wkt: str) -> tuple:
    """Extrai (W, S, E, N) de WKT POLYGON."""
    nums = list(map(float, re.findall(r"[-\d.]+",
        wkt.replace("POLYGON", "").replace("(", "").replace(")", ""))))
    lons = nums[0::2]
    lats = nums[1::2]
    return (min(lons), min(lats), max(lons), max(lats))  # W, S, E, N


def _login(user: str, pwd: str):
    """Autentica via earthaccess usando variaveis de ambiente."""
    try:
        import earthaccess
    except ImportError:
        raise RuntimeError("Pacote 'earthaccess' nao instalado. Execute: pip install earthaccess")
    os.environ["EARTHDATA_USERNAME"] = user
    os.environ["EARTHDATA_PASSWORD"] = pwd
    earthaccess.login(strategy="environment")
    return earthaccess


def search(params: dict) -> list[dict]:
    """
    Busca granules SRTMGL1 v003 via CMR e extrai URLs HTTPS reais.

    params esperados:
        aoi_wkt    : str   (WKT polygon, obrigatorio)
        resolution : str   ("SRTMGL1" = 30m, "SRTMGL3" = 90m)
        earthdata_user : str
        earthdata_pass : str
    """
    aoi = (params.get("aoi_wkt") or "").strip()
    if not aoi:
        raise ValueError("AOI e obrigatorio para busca de tiles SRTM.")

    user = params.get("earthdata_user", os.environ.get("EARTHDATA_USERNAME", ""))
    pwd  = params.get("earthdata_pass", os.environ.get("EARTHDATA_PASSWORD", ""))
    short_name = params.get("resolution", "SRTMGL1")
    bbox = _wkt_to_bbox(aoi)   # (W, S, E, N)

    ea = _login(user, pwd)

    results = ea.search_data(
        short_name=short_name,
        version="003",
        bounding_box=bbox,
    )

    items = []
    for r in results:
        # Extrai URLs HTTPS reais — sobrevivem a serialização JSON
        urls = r.data_links(access="indirect")   # HTTPS (não S3)
        if not urls:
            urls = r.data_links()                 # qualquer URL disponivel

        if not urls:
            continue

        meta = r.get("umm", {})
        name = r["meta"].get("native-id", f"SRTM_{len(items)+1}")

        sizes = [
            f.get("Size", 0)
            for f in meta.get("DataGranule", {}).get(
                "ArchiveAndDistributionInformation", [])
        ]
        size_mb = round(sum(sizes), 1) if sizes else 25.0

        td = meta.get("TemporalExtent", {}).get("RangeDateTime", {})
        date = td.get("BeginningDateTime", "2000-02-11")[:10]

        for url in urls:
            items.append({
                "name":    name,
                "product": "SRTM 30m",
                "date":    date,
                "size_mb": size_mb,
                "url":     url,        # URL real extraida do earthaccess
                "thumb":   None,
                "bbox":    None,
            })
    return items


def download(products: list[dict], cfg: dict, log_fn=print) -> None:
    """
    Baixa tiles SRTM usando sessao autenticada do earthaccess.

    products : lista com campo 'url' (URL real extraida no search)
    cfg      : dict com 'earthdata' (username/password) e 'download.directory'
    """
    earthdata = cfg.get("earthdata", {})
    user = earthdata.get("username", "")
    pwd  = earthdata.get("password", "")

    if not user or not pwd:
        raise RuntimeError("Credenciais NASA Earthdata nao configuradas. Acesse Configuracoes.")

    out_dir = Path(cfg.get("download", {}).get("directory", "downloads/srtm"))
    out_dir.mkdir(parents=True, exist_ok=True)

    log_fn("Autenticando via NASA Earthdata (earthaccess)...")
    ea = _login(user, pwd)
    log_fn(f"  Autenticado como: {user}")

    # Sessao requests autenticada gerenciada pelo earthaccess
    session = ea.get_requests_https_session()

    log_fn(f"Iniciando download de {len(products)} tile(s) SRTM...")
    for i, prod in enumerate(products, 1):
        url  = prod.get("url", "")
        name = prod.get("name", f"tile_{i}")
        filename = url.split("/")[-1] or f"{name}.hgt.zip"
        log_fn(f"[{i}/{len(products)}] {filename}")
        log_fn(f"  URL: {url}")

        try:
            out_path = out_dir / filename
            with session.get(url, stream=True, timeout=120, allow_redirects=True) as r:
                if r.history:
                    log_fn(f"  -> {len(r.history)} redirect(s), final: {r.status_code}")
                r.raise_for_status()
                ct = r.headers.get("Content-Type", "")
                if "text/html" in ct:
                    log_fn(f"  Erro: recebeu HTML — autenticacao falhou")
                    break
                total = 0
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            total += len(chunk)
            log_fn(f"  OK: {filename} ({round(total/1e6, 1)} MB)")
        except Exception as e:
            log_fn(f"  Erro em {filename}: {e}")
