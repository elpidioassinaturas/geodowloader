---
name: versioning
description: >
  Fluxo de versionamento para o GeoDownloader.
  Gerencia os três estados do app (desenvolvimento/beta/produção),
  incrementa a versão conforme o tipo de mudança (novo dataset ou
  alteração de código), faz commit e adiciona entrada no CHANGELOG.md.
---

# Skill: Versionamento GeoDownloader

Use este skill **sempre** que alterar ou criar código no projeto.

---

## Esquema de Versão

Formato: `MAJOR.MINOR.PATCH`

| Campo   | Desenvolvimento | Beta | Produção |
|---------|:-:|:-:|:-:|
| `MAJOR` | 0 | 0 | 1 |
| `MINOR` | 1 | 9 | 0 |
| `PATCH` | incremental | incremental | incremental |

**Estado atual** armazenado no arquivo `VERSION` na forma:
```
<MAJOR>.<MINOR>.<PATCH>
```

### Quando incrementar o PATCH

| Evento | Incremento |
|--------|-----------|
| Alteração de código (bugfix, melhoria, refactor) | +1 |
| Novo dataset adicionado (nova aba/fonte) | +10 |

**Versão inicial:** `0.1.001` (desenvolvimento, sem datasets)

---

## Arquivo de Estado: `APP_STATE`

Crie/mantenha o arquivo `APP_STATE` na raiz com um dos três valores:
```
development
beta
production
```

**Para mudança de estado**, atualize `APP_STATE` E a versão:
- `development → beta`: troque `0.1.XXX` → `0.9.XXX`
- `beta → production`: troque `0.9.XXX` → `1.0.XXX`

---

## Passos a executar a cada mudança

### 1. Ler versão e estado atuais

```powershell
$version = (Get-Content VERSION).Trim()
$state   = (Get-Content APP_STATE).Trim()
Write-Host "Estado: $state | Versão: $version"
```

### 2. Calcular nova versão

**Para alteração de código** (incremento +1 no PATCH):
```powershell
$parts    = $version.Split(".")
$patch    = [int]$parts[2] + 1
$newVersion = "$($parts[0]).$($parts[1]).$($patch.ToString('D3'))"
```

**Para novo dataset** (incremento +10 no PATCH):
```powershell
$parts    = $version.Split(".")
$patch    = [int]$parts[2] + 10
$newVersion = "$($parts[0]).$($parts[1]).$($patch.ToString('D3'))"
```

```powershell
# Gravar nova versão
$newVersion | Set-Content VERSION
Write-Host "Versão: $version → $newVersion"
```

### 3. Atualizar `doc/CHANGELOG.md`

Adicione no **TOPO** do arquivo:

```markdown
## [X.Y.ZZZ] — AAAA-MM-DD — <descrição curta>

**Commit:** <hash_curto>
**Estado:** development | beta | production

### Adicionado
- ...

### Modificado
- ...

### Corrigido
- ...

### Removido
- ...
```

### 4. Stage e commit

```powershell
git add -A
$hash = git commit -m "v$newVersion — <DESCRIÇÃO>" --format="%h" | Select-String "master|HEAD" | ...
git commit -m "v$newVersion — <DESCRIÇÃO>"
```

> **Mensagem de commit:** `v0.1.002 — Adiciona adapter Sentinel-1`

### 5. Recuperar hash e atualizar CHANGELOG

```powershell
$hash = git log -1 --format="%h"
Write-Host "Hash do commit: $hash"
# Edite manualmente o CHANGELOG para incluir o hash real
```

### 6. Push

```powershell
git push origin master
```

---

## Script completo (PowerShell)

Copie e adapte conforme o tipo de mudança (+1 ou +10):

```powershell
# ── Parâmetros ──────────────────────────────────────────────────────────
$descricao   = "DESCREVA A MUDANÇA AQUI"
$incremento  = 1        # 1 para código, 10 para novo dataset
$hoje        = Get-Date -Format "yyyy-MM-dd"

# ── Ler estado atual ─────────────────────────────────────────────────────
$version = (Get-Content VERSION).Trim()
$state   = (Get-Content APP_STATE).Trim()
$parts   = $version.Split(".")

# ── Calcular nova versão ─────────────────────────────────────────────────
$patch      = [int]$parts[2] + $incremento
$newVersion = "$($parts[0]).$($parts[1]).$($patch.ToString('D3'))"
$newVersion | Set-Content VERSION
Write-Host "Versão: $version → $newVersion"

# ── Commit ───────────────────────────────────────────────────────────────
git add -A
git commit -m "v$newVersion — $descricao"
$hash = git log -1 --format="%h"
Write-Host "Commit: $hash"

# ── Atualizar CHANGELOG ──────────────────────────────────────────────────
$entry = @"

## [$newVersion] — $hoje — $descricao

**Commit:** $hash
**Estado:** $state

### Modificado
- $descricao

"@
$old = Get-Content doc\CHANGELOG.md -Raw
$entry + $old | Set-Content doc\CHANGELOG.md -Encoding UTF8
Write-Host "CHANGELOG atualizado."

# ── Push ─────────────────────────────────────────────────────────────────
git push origin master
Write-Host "Push concluído: v$newVersion"
```

---

## Notas

- `config.yaml` está no `.gitignore` — credenciais NUNCA são versionadas
- O hash do commit é adicionado automaticamente ao CHANGELOG
- Quando adicionar um novo dataset, use `$incremento = 10`
- Quando mudar de estado (dev→beta→prod), atualize MAJOR e MINOR manualmente
