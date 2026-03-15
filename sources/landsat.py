#!/usr/bin/env python3
"""
sources/landsat.py
==================
Adapter Landsat 8/9 — NASA Earthdata via earthaccess (LP DAAC Collection 2).

Produtos disponíveis:
  LANDSAT_OT_C2_L2  — Collection 2 Level-2 (reflectância de superfície) L8+L9
  LANDSAT_OT_C2_L1  — Collection 2 Level-1 (radiância no topo) L8+L9

Credencial: NASA Earthdata (username + password)
Referência: https://lpdaac.usgs.gov/products/landsat-collection-2/

Mesmo padrão earthaccess do SRTM:
  search() autentica via earthaccess, busca via CMR, extrai URLs HTTPS reais.
  download() usa get_requests_https_session() com auth transparente.
"""
from __future__ import annotations
import os
import re
from pathlib import Path

# Mapeamento missão → short_name CMR + platform
_MISSION = {
    "LANDSAT_8": {
        "short_name": "LANDSAT_OT_C2_L2",
        "version":    "002",
        "platform":   "LANDSAT-8",
    },
    "LANDSAT_9": {
        "short_name": "LANDSAT_OT_C2_L2",
        "version":    "002",
        "platform":   "LANDSAT-9",
    },
    "LANDSAT_8_L1": {
        "short_name": "LANDSAT_OT_C2_L1",
        "version":    "002",
        "platform":   "LANDSAT-8",
    },
    "LANDSAT_9_L1": {
        "short_name": "LANDSAT_OT_C2_L1",
        "version":    "002",
        "platform":   "LANDSAT-9",
    },
}


def _wkt_to_bbox(wkt: str) -> tuple:
    """Extrai (W, S, E, N) de WKT POLYGON."""
    nums = list(map(float, re.findall(r"[-\d.]+",
        wkt.replace("POLYGON", "").replace("(", "").replace(")", ""))))
    lons = nums[0::2]
    lats = nums[1::2]
    return (min(lons), min(lats), max(lons), max(lats))


def _login(user: str, pwd: str):
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
    Busca cenas Landsat 8/9 Collection 2 Level-2 via CMR (earthaccess).

    params esperados:
        aoi_wkt         : str   (WKT polygon, obrigatorio)
        product_type    : str   (LANDSAT_8 | LANDSAT_9, default LANDSAT_9)
        start_date      : str   (YYYY-MM-DD)
        end_date        : str   (YYYY-MM-DD)
        cloud_cover     : int   (0-100, default 30)
        max_results     : int   (default 50)
        earthdata_user  : str
        earthdata_pass  : str
    """
    aoi = (params.get("aoi_wkt") or "").strip()
    if not aoi:
        raise ValueError("AOI e obrigatorio para busca de cenas Landsat.")

    user = params.get("earthdata_user", os.environ.get("EARTHDATA_USERNAME", ""))
    pwd  = params.get("earthdata_pass", os.environ.get("EARTHDATA_PASSWORD", ""))

    mission     = params.get("product_type", "LANDSAT_9")
    start_date  = params.get("start_date", "2024-01-01")
    end_date    = params.get("end_date",   "2024-12-31")
    cloud_max   = int(params.get("cloud_cover", 30))
    max_results = int(params.get("max_results", 50))

    mission_cfg = _MISSION.get(mission, _MISSION["LANDSAT_9"])
    bbox = _wkt_to_bbox(aoi)   # (W, S, E, N)

    ea = _login(user, pwd)

    # Busca via CMR
    results = ea.search_data(
        short_name   = mission_cfg["short_name"],
        version      = mission_cfg["version"],
        bounding_box = bbox,
        temporal     = (start_date, end_date),
        cloud_cover  = (0, cloud_max),
        count        = max_results,
    )

    items = []
    for r in results:
        # URLs HTTPS reais — sobrevivem serialização JSON
        urls = r.data_links(access="indirect") or r.data_links()
        if not urls:
            continue

        meta = r.get("umm", {})
        name = r["meta"].get("native-id", f"Landsat_{len(items)+1}")

        # Tamanho estimado
        sizes = [
            f.get("Size", 0)
            for f in meta.get("DataGranule", {}).get(
                "ArchiveAndDistributionInformation", [])
        ]
        size_mb = round(sum(sizes), 1) if sizes else 800.0

        # Data de aquisição
        td   = meta.get("TemporalExtent", {}).get("RangeDateTime", {})
        date = td.get("BeginningDateTime", start_date)[:10]

        # Cobertura de nuvens
        adds = meta.get("AdditionalAttributes", [])
        cloud = next(
            (a.get("Values", [None])[0]
             for a in adds if a.get("Name") == "CLOUD_COVER"),
            None,
        )
        cloud_pct = f"{float(cloud):.1f}%" if cloud is not None else "?"

        # Thumbnail
        browse = meta.get("RelatedUrls", [])
        thumb  = next(
            (b.get("URL") for b in browse if b.get("Type") == "GET RELATED VISUALIZATION"),
            None,
        )

        # Uma entrada por URL (cada cena tem vários arquivos — bandas)
        # Agrupa todas as URLs como uma cena única, usando a primeira URL como referência
        items.append({
            "name":      name,
            "product":   f"Landsat {mission.split('_')[1]} C2-L2",
            "date":      date,
            "cloud":     cloud_pct,
            "size_mb":   size_mb,
            "url":       urls[0],          # URL principal (index)
            "all_urls":  urls,             # todas as URLs das bandas
            "thumb":     thumb,
            "bbox":      None,
        })

    return items


def download(products: list[dict], cfg: dict, log_fn=print) -> None:
    """
    Baixa cenas Landsat usando sessao autenticada earthaccess.

    products : lista com campos 'url' e opcionalmente 'all_urls'
    cfg      : dict com 'earthdata' (username/password) e 'download.directory'
    """
    earthdata = cfg.get("earthdata", {})
    user = earthdata.get("username", "")
    pwd  = earthdata.get("password", "")

    if not user or not pwd:
        raise RuntimeError("Credenciais NASA Earthdata nao configuradas. Acesse Configuracoes.")

    out_dir = Path(cfg.get("download", {}).get("directory", "downloads/landsat"))
    out_dir.mkdir(parents=True, exist_ok=True)

    log_fn("Autenticando via NASA Earthdata (earthaccess)...")
    ea = _login(user, pwd)
    session = ea.get_requests_https_session()
    log_fn(f"  Autenticado como: {user}")

    log_fn(f"Iniciando download de {len(products)} cena(s) Landsat...")

    for i, prod in enumerate(products, 1):
        name     = prod.get("name", f"cena_{i}")
        all_urls = prod.get("all_urls") or [prod.get("url", "")]
        log_fn(f"[{i}/{len(products)}] {name} — {len(all_urls)} arquivo(s)")

        # Subpasta por cena
        scene_dir = out_dir / name
        scene_dir.mkdir(exist_ok=True)

        for url in all_urls:
            filename = url.split("/")[-1].split("?")[0] or "file"
            out_path = scene_dir / filename
            if out_path.exists():
                log_fn(f"  Ja existe: {filename}")
                continue
            try:
                with session.get(url, stream=True, timeout=180, allow_redirects=True) as r:
                    ct = r.headers.get("Content-Type", "")
                    if "text/html" in ct or r.status_code in (401, 403):
                        log_fn(f"  Erro de autenticacao ({r.status_code})")
                        break
                    r.raise_for_status()
                    total = 0
                    with open(out_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=2 * 1024 * 1024):
                            if chunk:
                                f.write(chunk)
                                total += len(chunk)
                log_fn(f"  OK: {filename} ({round(total/1e6, 1)} MB)")
            except Exception as e:
                log_fn(f"  Erro em {filename}: {e}")

        log_fn(f"  Cena salva em: {scene_dir}")
