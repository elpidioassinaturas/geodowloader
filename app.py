#!/usr/bin/env python3
"""
app.py — GeoDownloader
======================
Interface Web Flask para busca e download de múltiplas fontes de dados raster.
Versão: 0.1.001 | Estado: development
"""
import json
import os
import queue
import threading
from datetime import datetime
from pathlib import Path

import yaml
from flask import Flask, Response, jsonify, render_template, request

# ── Imports opcionais ─────────────────────────────────────────────────────────
try:
    from geodata import south_america_countries, geocode_area, load_aoi_file
except ImportError:
    south_america_countries = lambda: []
    geocode_area  = None
    load_aoi_file = None

# ── Adapters de fontes ────────────────────────────────────────────────────────
_ADAPTERS = {}

def _load_adapter(name: str):
    if name not in _ADAPTERS:
        try:
            import importlib
            mod = importlib.import_module(f"sources.{name}")
            _ADAPTERS[name] = mod
        except ImportError:
            _ADAPTERS[name] = None
    return _ADAPTERS[name]

# ── App Flask ─────────────────────────────────────────────────────────────────
app = Flask(__name__)

CONFIG_PATH = Path("config.yaml")
VERSION     = (Path("VERSION").read_text(encoding="utf-8").strip()
               if Path("VERSION").exists() else "0.1.001")
APP_STATE   = (Path("APP_STATE").read_text(encoding="utf-8").strip()
               if Path("APP_STATE").exists() else "development")

LOG_QUEUE:      queue.Queue = queue.Queue()
DOWNLOAD_STATUS = {"running": False, "done": 0, "total": 0, "error": None, "source": ""}

# ── Config helpers ─────────────────────────────────────────────────────────────
def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def save_config(data: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

# ── Routes — Página principal ──────────────────────────────────────────────────
@app.route("/")
def index():
    from sources import CATEGORIES, DATASET_LABELS
    return render_template("index.html",
                           version=VERSION,
                           app_state=APP_STATE,
                           categories=CATEGORIES,
                           dataset_labels=DATASET_LABELS)

# ── Routes — Config ────────────────────────────────────────────────────────────
@app.route("/api/config", methods=["GET"])
def get_config():
    cfg = load_config()
    return jsonify({
        "earthdata":  cfg.get("earthdata",  {"username": "", "password": ""}),
        "copernicus": cfg.get("copernicus", {"email":    "", "password": ""}),
        "cds":        cfg.get("cds",        {"uid":      "", "api_key": ""}),
        "download":   cfg.get("download",   {"directory": "downloads", "processes": 2}),
    })

@app.route("/api/config", methods=["POST"])
def post_config():
    d = request.json or {}
    cfg = load_config()
    # Credenciais por provedor
    if "earthdata" in d:
        cfg["earthdata"] = d["earthdata"]
    if "copernicus" in d:
        cfg["copernicus"] = d["copernicus"]
    if "cds" in d:
        cfg["cds"] = d["cds"]
    if "download" in d:
        cfg["download"] = d["download"]
    save_config(cfg)
    return jsonify({"ok": True})

# ── Routes — Versão / Estado ───────────────────────────────────────────────────
@app.route("/api/version")
def api_version():
    return jsonify({"version": VERSION, "state": APP_STATE})

# ── Routes — Datasets disponíveis ─────────────────────────────────────────────
@app.route("/api/datasets")
def api_datasets():
    from sources import CATEGORIES, DATASET_LABELS
    return jsonify({"categories": CATEGORIES, "labels": DATASET_LABELS})

# ── Routes — Variáveis ERA5 ────────────────────────────────────────────────────
@app.route("/api/era5/variables")
def api_era5_variables():
    mod = _load_adapter("era5")
    if not mod:
        return jsonify({"variables": []})
    return jsonify({"variables": mod.list_variables()})

# ── Routes — Busca genérica ────────────────────────────────────────────────────
@app.route("/api/<source>/search", methods=["POST"])
def api_search(source: str):
    mod = _load_adapter(source)
    if not mod:
        return jsonify({"error": f"Fonte '{source}' não disponível ou não instalada"}), 404

    cfg    = load_config()
    params = request.json or {}

    # Injeta configurações globais de download
    params.setdefault("download_dir", cfg.get("download", {}).get("directory", "downloads"))

    # Injeta credenciais Earthdata nos params (necessário para earthaccess no search)
    ed = cfg.get("earthdata", {})
    if ed.get("username"):
        params.setdefault("earthdata_user", ed["username"])
        params.setdefault("earthdata_pass", ed["password"])

    try:
        results = mod.search(params)
        return jsonify({"results": results, "total": len(results), "source": source})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "detail": traceback.format_exc()}), 500

# ── Routes — Download genérico ─────────────────────────────────────────────────
def _download_worker(source: str, products: list, cfg: dict):
    global DOWNLOAD_STATUS
    DOWNLOAD_STATUS.update({"running": True, "done": 0, "total": len(products),
                             "error": None, "source": source})
    try:
        mod = _load_adapter(source)
        if not mod:
            raise RuntimeError(f"Adapter '{source}' não disponível")

        # Diretório específico por fonte
        dl_cfg = dict(cfg)
        dl_dir = cfg.get("download", {}).get("directory", "downloads")
        dl_cfg["download"] = {"directory": f"{dl_dir}/{source}",
                              "processes": cfg.get("download", {}).get("processes", 2)}

        def log(msg):
            LOG_QUEUE.put(msg)
            if msg.startswith("  ✓"):
                DOWNLOAD_STATUS["done"] += 1

        mod.download(products, dl_cfg, log_fn=log)
        LOG_QUEUE.put("__DONE__")
    except Exception as e:
        DOWNLOAD_STATUS["error"] = str(e)
        LOG_QUEUE.put(f"Erro: {e}")
        LOG_QUEUE.put("__DONE__")
    finally:
        DOWNLOAD_STATUS["running"] = False

@app.route("/api/<source>/download", methods=["POST"])
def api_download(source: str):
    if DOWNLOAD_STATUS["running"]:
        return jsonify({"error": "Download já em andamento"}), 400

    data     = request.json or {}
    products = data.get("results", [])
    if not products:
        return jsonify({"error": "Nenhum produto selecionado"}), 400

    cfg = load_config()

    # Limpa fila de log anterior
    while not LOG_QUEUE.empty():
        try: LOG_QUEUE.get_nowait()
        except: break

    t = threading.Thread(target=_download_worker, args=(source, products, cfg), daemon=True)
    t.start()
    return jsonify({"ok": True, "total": len(products), "source": source})

# ── Routes — SSE stream de log ─────────────────────────────────────────────────
@app.route("/api/stream")
def api_stream():
    def gen():
        while True:
            try:
                msg = LOG_QUEUE.get(timeout=30)
                yield f"data: {json.dumps({'msg': msg})}\n\n"
                if msg == "__DONE__":
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'msg': '__PING__'})}\n\n"
    return Response(gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.route("/api/status")
def api_status():
    return jsonify(DOWNLOAD_STATUS)

# ── Routes — Proxy de thumbnails autenticados ──────────────────────────────────
@app.route("/api/proxy/thumb")
def api_proxy_thumb():
    """
    Proxy para thumbnails que requerem autenticação (ex: USGS LandsatLook).
    Uso: /api/proxy/thumb?url=https://landsatlook.usgs.gov/.../thumb.jpeg
    """
    import requests as _req
    url = request.args.get("url", "")
    if not url or not url.startswith("https://"):
        return Response(status=400)

    cfg = load_config()
    ed  = cfg.get("earthdata", {})
    user = ed.get("username", "")
    pwd  = ed.get("password", "")

    try:
        headers = {"User-Agent": "GeoDownloader/1.0"}
        if user and pwd:
            resp = _req.get(url, auth=(user, pwd), timeout=15,
                            allow_redirects=True, headers=headers)
        else:
            resp = _req.get(url, timeout=15, allow_redirects=True, headers=headers)

        content_type = resp.headers.get("Content-Type", "image/jpeg")
        if resp.status_code != 200 or "text/html" in content_type:
            return Response(status=404)

        return Response(resp.content, content_type=content_type,
                        headers={"Cache-Control": "public, max-age=3600"})
    except Exception:
        return Response(status=502)

# ── Routes — Arquivos baixados ─────────────────────────────────────────────────
@app.route("/api/files")
def api_files():
    cfg     = load_config()
    base    = Path(cfg.get("download", {}).get("directory", "downloads"))
    source  = request.args.get("source", "")
    scan_dir = base / source if source else base

    files = []
    if scan_dir.exists():
        for f in sorted(scan_dir.rglob("*")):
            if f.is_file():
                files.append({
                    "name":     f.name,
                    "source":   f.parent.name,
                    "size_mb":  round(f.stat().st_size / 1e6, 1),
                    "date":     datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                    "path":     str(f),
                })
    return jsonify({"files": files})

# ── Routes — Geocoding / AOI ───────────────────────────────────────────────────
@app.route("/api/countries")
def api_countries():
    return jsonify({"countries": south_america_countries()})

@app.route("/api/geocode", methods=["POST"])
def api_geocode():
    if not geocode_area:
        return jsonify({"error": "geodata.py não carregado"}), 500
    d       = request.json or {}
    country = d.get("country", "")
    state   = d.get("state", "")
    muni    = d.get("municipality", "")
    if not country:
        return jsonify({"error": "País obrigatório"}), 400
    result = geocode_area(country, state, muni)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result)

@app.route("/api/upload-aoi", methods=["POST"])
def api_upload_aoi():
    if not load_aoi_file:
        return jsonify({"error": "geodata.py não carregado"}), 500
    if "file" not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400
    f        = request.files["file"]
    filename = f.filename or ""
    if not filename.lower().endswith((".zip", ".gpkg")):
        return jsonify({"error": "Use .zip (shapefile) ou .gpkg"}), 400
    result = load_aoi_file(f.read(), filename)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)

# ── Main ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import webbrowser
    print("=" * 55)
    print(f"  GeoDownloader v{VERSION} [{APP_STATE.upper()}]")
    print("  Abrindo em: http://localhost:5000")
    print("  Para encerrar: feche esta janela ou Ctrl+C")
    print("=" * 55)
    threading.Timer(1.2, lambda: webbrowser.open("http://localhost:5000")).start()
    app.run(debug=False, host="127.0.0.1", port=5000)
