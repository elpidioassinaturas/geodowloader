
## [0.1.016]  2026-03-15  srtm.py: product name corrigido para SRTM 30m nos resultados de busca

**Commit:** c0433d5  |  **Estado:** development

### Corrigido
- sources/srtm.py: campo 'product' nos resultados alterado de 'CopDEM GLO-30'
  para 'SRTM 30m' — resultados de busca agora mostram SRTM conforme esperado
- sources/__init__.py: label 'srtm' revertido para 'SRTM 30m' (corrige duplicata na aba MDE)

## [0.1.015]  2026-03-15  label srtm -> CopDEM GLO-30, remove credencial requerida, update info text

**Commit:** b101438  |  **Estado:** development

### Corrigido
- sources/__init__.py: label 'srtm' alterado de 'SRTM 30m' para 'CopDEM GLO-30'
- sources/__init__.py: credencial requerida removida (AWS S3 e publico)
- templates/index.html: info text atualizado para explicar uso do CopDEM

## [0.1.014]  2026-03-15  srtm.py: troca NASA LP DAAC (URL quebrada) por CopDEM GLO-30 AWS S3 publico sem auth

**Commit:** 6be40a2  |  **Estado:** development

### Alterado
- sources/srtm.py: substituido por Copernicus DEM GLO-30 via AWS S3 Open Data
- Motivo: URL do NASA LP DAAC retornava 404 direto (sem redirect de auth)
  indicando que a URL do SRTMGL1.003 no servidor esta desatualizada/migrada
- CopDEM GLO-30: mesmo tile scheme 1x1deg, ~30m, derivado TanDEM-X (2010-2015)
- Sem autenticacao requerida  bucket S3 publico copernicus-dem-30m.s3.amazonaws.com
- Naming: Copernicus_DSM_COG_10_{NS}{lat}_00_{EW}{lon}_00_DEM.tif

## [0.1.013]  2026-03-15  SRTM: auth como tupla (padrao NASA), log de redirect history para diagnostico

**Commit:** a020050
**Estado:** development

### Corrigido
- EarthdataSession: implementação agora usa padrão oficial NASA Wiki
  (mantém Authorization apenas para redirects to/from urs.earthdata.nasa.gov)
- session.auth definido como TUPLA (user, pwd) em vez de HTTPBasicAuth
- Adicionado log completo do histórico de redirects para diagnóstico

## [0.1.012]  2026-03-15  Corrige autenticacao SRTM: EarthdataSession repassa credenciais no redirect OAuth NASA

**Commit:** c1c8c94
**Estado:** development

### Corrigido
- sources/srtm.py: substituído HTTPBasicAuth simples por EarthdataSession que
  sobrescreve rebuild_auth para repassar credenciais no redirect OAuth da NASA
  (urs.earthdata.nasa.gov). Antes o redirect retornava 404 pois as credenciais
  não eram enviadas ao URL de destino.
- Detecta resposta HTML (página de login) em vez do arquivo .zip
- Adiciona verificação de credenciais vazias antes do download
- Melhora mensagens de diagnóstico (status 401/403, URL redirecionada)

## [0.1.011] — 2026-03-15 — Estrutura inicial do GeoDownloader: app.py, geodata.py, 6 adapters (nisar/sentinel1/sentinel2/srtm/era5/chirps), templates/index.html UI completa

**Commit:** 84735d2
**Estado:** development

### Adicionado
- app.py: Flask com roteamento genérico /api/<source>/search e /api/<source>/download
- geodata.py: geocoding via Nominatim + leitura shapefile/gpkg (portado do NISAR)
- sources/nisar.py: adapter NISAR via asf_search
- sources/sentinel1.py: adapter Sentinel-1 via CDSE OData + OAuth2
- sources/sentinel2.py: adapter Sentinel-2 com filtro de nuvens
- sources/srtm.py: adapter SRTM 30m com geração automática de tiles por AOI
- sources/era5.py: adapter ERA5 via cdsapi
- sources/chirps.py: adapter CHIRPS (HTTP direto, sem autenticação)
- templates/index.html: UI completa  abas categoria/dataset, modal AOI Leaflet tela cheia, drawer credenciais por provedor, SSE progress
- config.yaml.example, requirements.txt, INICIAR.bat
# Changelog — GeoDownloader

Todas as versões notáveis deste projeto estão documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

---

## [0.1.001] — 2026-03-15 — Inicialização do projeto

**Commit:** (inicial)
**Estado:** development

### Adicionado
- Repositório Git e GitHub criados
- `.gitignore` configurado para Python/Flask
- Skill de versionamento customizado (`versioning`)
- Arquivos `VERSION` e `APP_STATE`
- `doc/CHANGELOG.md`






