
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



