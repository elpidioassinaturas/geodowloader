#!/usr/bin/env python3
"""
sources/chirps.py
=================
Adapter CHIRPS — Climate Hazards Group InfraRed Precipitation with Station data.
Download direto via HTTP (sem autenticação).

Resolução: 0.05° (~5.5km) | Cobertura: 50°S-50°N | Período: 1981-presente
URL: https://data.chc.ucsb.edu/products/CHIRPS-2.0/
"""
from __future__ import annotations
from pathlib import Path
import requests

_BASE_URL = "https://data.chc.ucsb.edu/products/CHIRPS-2.0"


def search(params: dict) -> list[dict]:
    """
    Gera lista de arquivos CHIRPS mensais para o período solicitado.

    params esperados:
        start_date : str  (YYYY-MM)
        end_date   : str  (YYYY-MM)
        resolution : str  ("p05" = 0.05° ou "p25" = 0.25°)
    """
    start = params.get("start_date", "2024-01")
    end   = params.get("end_date",   "2024-12")
    res   = params.get("resolution", "p05")

    start_y, start_m = map(int, start.split("-"))
    end_y,   end_m   = map(int, end.split("-"))

    items = []
    y, m = start_y, start_m
    while (y, m) <= (end_y, end_m):
        filename = f"chirps-v2.0.{y}.{m:02d}.tif.gz"
        url = f"{_BASE_URL}/global_monthly/tifs/{filename}"
        items.append({
            "name":    filename.replace(".tif.gz", ""),
            "product": f"CHIRPS {res}",
            "date":    f"{y}-{m:02d}",
            "size_mb": 30.0,  # aproximado
            "url":     url,
            "file":    filename,
            "thumb":   None,
            "bbox":    None,
        })
        m += 1
        if m > 12:
            m = 1
            y += 1
    return items


def download(products: list[dict], cfg: dict, log_fn=print) -> None:
    """
    Baixa arquivos CHIRPS (sem autenticação).
    """
    out_dir = Path(cfg.get("download", {}).get("directory", "downloads/chirps"))
    out_dir.mkdir(parents=True, exist_ok=True)

    log_fn(f"Iniciando download de {len(products)} arquivo(s) CHIRPS...")
    for i, prod in enumerate(products, 1):
        filename = prod.get("file", prod.get("name", f"chirps_{i}.tif.gz"))
        url      = prod.get("url", "")
        log_fn(f"[{i}/{len(products)}] Baixando: {filename}")
        try:
            out_path = out_dir / filename
            with requests.get(url, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        f.write(chunk)
            log_fn(f"  ✓ Concluído: {filename}")
        except Exception as e:
            log_fn(f"  ✗ Erro em {filename}: {e}")
