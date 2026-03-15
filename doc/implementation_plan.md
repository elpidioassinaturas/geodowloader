# GeoDownloader — Plano de Implementação

App web local (Flask) para busca e download de múltiplas fontes de dados raster, reutilizando a arquitetura do app NISAR existente.

**Decisões de UI aprovadas:**
- Layout 2 níveis: abas de categoria (Radar / Óptico / MDE / Clima) → sub-abas de dataset
- **AOI: botão no painel direito abre modal em tela cheia** com Leaflet, ferramentas de desenho, busca por localidade e upload de shapefile
- Painel principal mostra preview compacto da AOI selecionada (WKT resumido + bbox)
- Drawer ⚙️ no header para credenciais, agrupadas por provedor

## Arquitetura Geral

```
geodowloader/
├── app.py                  # Flask principal — roteamento multi-fonte
├── geodata.py              # Geocoding + AOI (copiado do NISAR, sem alteração)
├── sources/
│   ├── __init__.py
│   ├── nisar.py            # Adapter NISAR (ASF DAAC / asf_search)
│   ├── sentinel.py         # Adapter Sentinel-1/2 (Copernicus Browser API)
│   ├── srtm.py             # Adapter SRTM / Copernicus DEM
│   └── era5.py             # Adapter ERA5 (CDS API / cdsapi)
├── templates/
│   └── index.html          # UI single-page multi-fonte com Leaflet + abas
├── config.yaml.example     # Template de configuração (credenciais + parâmetros)
├── requirements.txt
├── INICIAR.bat             # Launcher Windows
└── VERSION
```

## Padrão de Adaptador (sources/)

Cada fonte implementa a mesma interface:

```python
def search(params: dict) -> list[dict]      # Retorna lista de produtos
def download(products: list, cfg: dict, log_fn) -> None  # Download com callback de log
```

Isso permite que `app.py` roteie via `/api/{source}/search` e `/api/{source}/download` de forma genérica.

---

## Proposed Changes

### Core App

#### [NEW] [app.py](file:///f:/R_project/geodowloader/app.py)
- Flask app com rotas genéricas `/api/<source>/search` e `/api/<source>/download`
- Mantém o padrão SSE (Server-Sent Events) com `queue.Queue` do NISAR
- Rotas de config (`/api/config` GET/POST) com suporte a seção por fonte
- Rota de geocoding e AOI upload (reaproveitado do NISAR)
- Rotas de listagem de arquivos locais

#### [NEW] [geodata.py](file:///f:/R_project/geodowloader/geodata.py)
- Cópia direta do `geodata.py` do NISAR (geocoding Nominatim + leitura de shapefile/gpkg)
- Sem alterações

#### [NEW] [config.yaml.example](file:///f:/R_project/geodowloader/config.yaml.example)
- Seções por fonte: `nisar`, `sentinel`, `srtm`, `era5`
- Credenciais separadas por fonte (`earthdata`, `copernicus`, `cds`)

---

### Adapters

#### [NEW] [sources/nisar.py](file:///f:/R_project/geodowloader/sources/nisar.py)
- Porta o `download_nisar.py` original como módulo reutilizável
- `search(params)` → usa `asf_search`
- `download(products, cfg, log_fn)` → baixa com `ASFSession`

#### [NEW] [sources/sentinel.py](file:///f:/R_project/geodowloader/sources/sentinel.py)
- Busca via **Copernicus Data Space Ecosystem (CDSE)** OpenSearch API (sem autenticação para busca)
- Download via token OAuth2 do CDSE
- Suporta Sentinel-1 (SAR) e Sentinel-2 (óptico)

#### [NEW] [sources/srtm.py](file:///f:/R_project/geodowloader/sources/srtm.py)
- Download de tiles SRTM 1-arc (30m) via NASA EarthData ou Copernicus DEM GLO-30
- Usa `requests` com sessão Earthdata autenticada

#### [NEW] [sources/era5.py](file:///f:/R_project/geodowloader/sources/era5.py)
- Integração com CDS API via `cdsapi`
- Busca de variáveis climáticas (temperatura, precipitação, vento) por área e período

---

### Frontend

#### [NEW] [templates/index.html](file:///f:/R_project/geodowloader/templates/index.html)
- Dark mode, glassmorphism, Leaflet com Esri satellite tiles
- **Header:** Logo GeoDownloader · badge versão · badge estado (DEV/BETA/PROD) · botão ⚙️ Configurações
- **Abas de categoria:** 📡 Radar · 🌿 Óptico · ⛰️ MDE · 🌧️ Clima
- **Sub-abas de dataset** (aparecem ao selecionar a categoria): ex. Radar → NISAR · Sentinel-1 · ALOS
- **Layout principal — 1 coluna:**
  - Painel de parâmetros do dataset selecionado
  - Campo de AOI com preview resumido (bbox + WKT) + botão `🗺️ Selecionar no mapa`
  - Tabela de resultados · progresso SSE de download
- **Modal AOI (tela cheia)** — abre ao clicar `🗺️ Selecionar no mapa`:
  - Header: título · busca por localidade (País/Estado/Município) · Upload .zip/.gpkg · botão ✕ Fechar
  - Corpo: mapa Leaflet 100% altura com tiles Esri satellite
  - Toolbar flutuante: ferramentas de polígono, retângulo, círculo, apagar (Leaflet.draw)
  - Rodapé: preview WKT monospace + botão ✅ Confirmar AOI · 🗑️ Limpar
- **Drawer de Configurações** (slide-in da direita):
  - Card 🌍 NASA Earthdata — usado por: NISAR, SRTM, Landsat, MODIS
  - Card 🇪🇺 Copernicus CDSE — usado por: Sentinel-1, Sentinel-2, CopDEM
  - Card 🌡️ CDS API — usado por: ERA5, CHIRPS
  - Botão 💾 Salvar · botão 🧪 Testar conexão
  - Status badge por credencial (✅ configurado / ⚠️ não configurado)

---

### Infraestrutura

#### [NEW] [requirements.txt](file:///f:/R_project/geodowloader/requirements.txt)
```
flask
pyyaml
requests
asf_search
rasterio>=1.3
cdsapi
fiona
shapely
```

#### [NEW] [INICIAR.bat](file:///f:/R_project/geodowloader/INICIAR.bat)
- Launcher Windows: cria venv se necessário, instala dependências, abre o browser

---

## User Review Required

> [!IMPORTANT]
> **Fontes de dados e credenciais necessárias:**
> | Fonte | Credencial | Como obter |
> |-------|-----------|------------|
> | NISAR | NASA Earthdata (já tem) | [urs.earthdata.nasa.gov](https://urs.earthdata.nasa.gov) |
> | Sentinel-1/2 | Copernicus CDSE | [dataspace.copernicus.eu](https://dataspace.copernicus.eu) (gratuito) |
> | SRTM (NASA) | NASA Earthdata (mesma do NISAR) | — |
> | ERA5 | CDS API Key | [cds.climate.copernicus.eu](https://cds.climate.copernicus.eu) (gratuito) |

> [!NOTE]
> **Escopo inicial:** Implementarei a UI completa e o sistema de roteamento. Os adapters terão `search()` e `download()` funcionais para NISAR e Sentinel. SRTM e ERA5 terão a estrutura pronta com funções básicas — você pode expandir conforme precisar das credenciais.

> [!NOTE]
> **Sem migração de dados:** O novo app é 100% independente do repositório `nisar`. Os dois coexistirão.

## Verification Plan

### Testes Manuais
1. Executar `INICIAR.bat` — verificar que o browser abre em `localhost:5000`
2. Testar seleção de fonte no dropdown do header
3. Testar mapa Leaflet — desenhar polígono AOI
4. Testar aba NISAR: preencher credenciais, clicar buscar
5. Verificar que o painel de log SSE recebe mensagens em tempo real
6. Verificar aba Sentinel: parâmetros específicos aparecem

---

## Coisas a Fazer

> Atualizado em: 2026-03-15

### 🔴 Alta Prioridade

- [ ] **Versão portátil (PyInstaller)**
  - [ ] Fase 1: Adaptar `app.py` com `BASE_DIR` dinâmico (modo .exe vs modo dev)
  - [ ] Fase 2: Criar `geodownloader.spec` (PyInstaller `--onedir`)
  - [ ] Fase 3: Criar `BUILD.bat` que gera o ZIP distribúivel
  - [ ] Fase 4: Resolver dependências problemáticas (earthaccess, GDAL, fiona)
  - [ ] Fase 5: Testar em VM limpa sem Python instalado
  - [ ] Fase 6: Publicar release no GitHub com `.zip`
  - *Detalhes completos em [`plano_versao_portatil.md`](plano_versao_portatil.md)*

### 🟡 Média Prioridade — Datasets Pendentes

- [ ] **Sentinel-1** — busca e download via Copernicus CDSE
- [ ] **Sentinel-2** — busca e download via Copernicus CDSE (thumbnail público)
- [ ] **Copernicus DEM** — download GLO-30/GLO-90 via AWS S3 (sem auth)
- [ ] **ERA5** — busca e download via CDS API (`cdsapi`)
- [ ] **CHIRPS** — download de precipitação via HTTP público (UCSB)

### 🟡 Média Prioridade — Melhorias Landsat

- [ ] Testar download real de cenas Landsat (auth USGS via earthaccess)
- [ ] Thumbnail nativo (requer login USGS ERS no browser do usuário)
- [ ] Suporte a Landsat 7 ETM+ (coleção `landsat-etm-c2-l2`)

### 🟢 Baixa Prioridade — Melhorias Gerais

- [ ] Ícone `.ico` para o executável portátil
- [ ] Barra de progresso com % real do download (baseada em `Content-Length`)
- [ ] Retomar download interrompido (verificar arquivos já existentes)
- [ ] Coluna "Nuvens" visível na tabela de resultados (Landsat/Sentinel)
- [ ] Filtro de data relativa (ex: "últimos 30 dias") nos parâmetros
- [ ] Suporte a múltiplas AOIs salvas / histórico de AOIs

### ✅ Concluído

- [x] NISAR — busca e download via asf_search
- [x] SRTM 30m — busca e download via earthaccess (NASA CMR)
- [x] Landsat 8/9 — busca via USGS LandsatLook STAC, filtro BOA/TOA/ST
- [x] Landsat — thumbnail (link visualizador 🔍) + cloud cover filter
- [x] INICIAR.bat corrigido (pip install sempre, mata porta 5000)
- [x] Proxy de thumbnail autenticado (`/api/proxy/thumb`)
