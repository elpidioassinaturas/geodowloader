#!/usr/bin/env python3
"""
sources/srtm.py
===============
Adapter SRTM 30m — NASA Earthdata via earthaccess (abordagem oficial LP DAAC).
Credencial: NASA Earthdata (username + password)

Referência oficial:
  https://github.com/nasa/LPDAAC-Data-Resources/blob/main/python/scripts/
  daac_data_download_python/DAACDataDownload.py

Usa a biblioteca earthaccess que gerencia o login Earthdata automaticamente.
Adicione ao requirements.txt: earthaccess
"""
from __future__ import annotations
import math
import re
from pathlib import Path


def _wkt_to_bbox(wkt: str) -> tuple:
    """Extrai (W, S, E, N) de WKT POLYGON."""
    nums = list(map(float, re.findall(r"[-\d.]+",
        wkt.replace("POLYGON", "").replace("(", "").replace(")", ""))))
    lons = nums[0::2]
    lats = nums[1::2]
    return (min(lons), min(lats), max(lons), max(lats))  # W, S, E, N


def search(params: dict) -> list[dict]:
    """
    Busca tiles SRTMGL1 v003 no NASA Earthdata via earthaccess.

    params esperados:
        aoi_wkt    : str  (WKT polygon, obrigatorio)
        resolution : str  ("SRTMGL1" = 30m, "SRTMGL3" = 90m)
    """
    try:
        import earthaccess
    except ImportError:
        raise RuntimeError(
            "Pacote 'earthaccess' nao instalado.\n"
            "Execute: pip install earthaccess"
        )

    aoi = (params.get("aoi_wkt") or "").strip()
    if not aoi:
        raise ValueError("AOI e obrigatorio para busca de tiles SRTM.")

    short_name = params.get("resolution", "SRTMGL1")
    bbox = _wkt_to_bbox(aoi)  # (W, S, E, N)

    results = earthaccess.search_data(
        short_name=short_name,
        version="003",
        bounding_box=bbox,
    )

    items = []
    for r in results:
        meta = r.get("umm", {})
        name = r["meta"].get("native-id", str(r))

        # Tamanho
        sizes = [
            f.get("Size", 0)
            for f in meta.get("DataGranule", {}).get("ArchiveAndDistributionInformation", [])
        ]
        size_mb = round(sum(sizes), 1) if sizes else 25.0

        # Data
        td = meta.get("TemporalExtent", {}).get("RangeDateTime", {})
        date = td.get("BeginningDateTime", "2000-02-11")[:10]

        items.append({
            "name":    name,
            "product": "SRTM 30m",
            "date":    date,
            "size_mb": size_mb,
            "url":     None,          # earthaccess gerencia as URLs internamente
            "_result": r,             # objeto earthaccess para uso no download
            "thumb":   None,
            "bbox":    None,
        })
    return items


def download(products: list[dict], cfg: dict, log_fn=print) -> None:
    """
    Baixa tiles SRTM usando earthaccess (abordagem oficial NASA LP DAAC).

    products : lista de dicts retornados por search(), com campo '_result'
    cfg      : dict com 'earthdata' (username/password) e 'download.directory'
    """
    try:
        import earthaccess
        import os
    except ImportError:
        raise RuntimeError("Pacote 'earthaccess' nao instalado. Execute: pip install earthaccess")

    earthdata = cfg.get("earthdata", {})
    user = earthdata.get("username", "")
    pwd  = earthdata.get("password", "")

    if not user or not pwd:
        raise RuntimeError("Credenciais NASA Earthdata nao configuradas. Acesse Configuracoes.")

    out_dir = Path(cfg.get("download", {}).get("directory", "downloads/srtm"))
    out_dir.mkdir(parents=True, exist_ok=True)

    # earthaccess suporta login via variaveis de ambiente
    os.environ["EARTHDATA_USERNAME"] = user
    os.environ["EARTHDATA_PASSWORD"] = pwd

    log_fn("Autenticando via NASA Earthdata (earthaccess)...")
    try:
        earthaccess.login(strategy="environment")
        log_fn(f"  Autenticado como: {user}")
    except Exception as e:
        raise RuntimeError(f"Falha no login Earthdata: {e}")

    # Recupera objetos earthaccess dos produtos selecionados
    ea_results = [p["_result"] for p in products if "_result" in p]

    if not ea_results:
        raise RuntimeError(
            "Produtos nao contem referencia earthaccess.\n"
            "Refaca a busca antes de baixar."
        )

    log_fn(f"Iniciando download de {len(ea_results)} tile(s) SRTM...")

    try:
        downloaded = earthaccess.download(ea_results, str(out_dir))
        for f in downloaded:
            size_mb = round(Path(f).stat().st_size / 1e6, 1) if Path(f).exists() else 0
            log_fn(f"  ✓ {Path(f).name} ({size_mb} MB)")
    except Exception as e:
        log_fn(f"  ✗ Erro no download: {e}")
        raise
