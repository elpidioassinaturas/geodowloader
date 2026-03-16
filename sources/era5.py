#!/usr/bin/env python3
"""
sources/era5.py
===============
Adapter ERA5 — download via CDS API (cdsapi).
Credencial: CDS API Key (uid + api_key em ~/.cdsapirc ou via config)

Variáveis disponíveis: temperatura, precipitação, vento, pressão, etc.
"""
from __future__ import annotations
from pathlib import Path
import os


_VARIABLES_AVAILABLE = [
    "2m_temperature",
    "total_precipitation",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "surface_pressure",
    "mean_sea_level_pressure",
    "skin_temperature",
    "soil_temperature_level_1",
    "volumetric_soil_water_layer_1",
    "evaporation",
    "runoff",
]


def list_variables() -> list[str]:
    return _VARIABLES_AVAILABLE


def search(params: dict) -> list[dict]:
    """
    ERA5 não tem busca de granules — retorna um único 'produto' descrevendo
    o request que será feito ao CDS.

    params esperados:
        variables    : list[str]  (ex: ["2m_temperature", "total_precipitation"])
        start_date   : str  (YYYY-MM)
        end_date     : str  (YYYY-MM)
        aoi_wkt      : str  (opcional, usado para extrair bbox)
    """
    variables = params.get("variables", ["2m_temperature"])
    start = params.get("start_date", "2024-01")
    end   = params.get("end_date",   "2024-12")
    aoi   = (params.get("aoi_wkt") or "").strip()

    # Monta nome descritivo
    vars_str = "+".join(variables[:3]) + ("…" if len(variables) > 3 else "")
    name = f"ERA5_{start}_{end}_{vars_str}"

    return [{
        "name":      name,
        "product":   "ERA5 Reanalysis",
        "date":      f"{start} → {end}",
        "size_mb":   None,  # depende do período/variáveis
        "url":       "https://cds.climate.copernicus.eu",
        "variables": variables,
        "start":     start,
        "end":       end,
        "aoi_wkt":   aoi,
        "thumb":     None,
        "bbox":      None,
    }]


def download(products: list[dict], cfg: dict, log_fn=print) -> None:
    """
    Baixa ERA5 via cdsapi.

    Requer que cdsapi esteja instalado e configurado.
    """
    try:
        import cdsapi
    except ImportError:
        raise RuntimeError("cdsapi não instalado. Execute: pip install cdsapi")

    cds_cfg = cfg.get("cds", {})
    cds_url = cds_cfg.get("url", "https://cds.climate.copernicus.eu/api")
    cds_key = cds_cfg.get("key", "") or cds_cfg.get("api_key", "")  # compatibilidade

    if not cds_key:
        raise RuntimeError(
            "Chave CDS não configurada. "
            "Acesse ⚙️ Configurações e preencha a Key do CDS API."
        )

    out_dir = Path(cfg.get("download", {}).get("directory", "downloads")) / "era5"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Configura credenciais via env vars (cdsapi lê CDSAPI_URL + CDSAPI_KEY)
    os.environ["CDSAPI_URL"] = cds_url
    os.environ["CDSAPI_KEY"] = cds_key

    client = cdsapi.Client(quiet=True)

    for prod in products:
        variables = prod.get("variables", ["2m_temperature"])
        start     = prod.get("start", "2024-01")
        end       = prod.get("end",   "2024-12")
        name      = prod.get("name", "era5_download")

        # Monta anos/meses
        from datetime import date
        start_y, start_m = map(int, start.split("-"))
        end_y,   end_m   = map(int, end.split("-"))
        years   = list(range(start_y, end_y + 1))
        months  = list(range(1, 13))

        request = {
            "product_type": "reanalysis",
            "variable":     variables,
            "year":         [str(y) for y in years],
            "month":        [f"{m:02d}" for m in months],
            "day":          [f"{d:02d}" for d in range(1, 32)],
            "time":         ["00:00", "06:00", "12:00", "18:00"],
            "data_format":  "netcdf",
            "download_format": "unarchived",
        }

        out_path = out_dir / f"{name}.nc"
        log_fn(f"Requisitando ERA5: {variables} | {start} → {end}")
        try:
            client.retrieve("reanalysis-era5-single-levels", request, str(out_path))
            log_fn(f"  ✓ Salvo: {out_path.name}")
        except Exception as e:
            log_fn(f"  ✗ Erro ERA5: {e}")
