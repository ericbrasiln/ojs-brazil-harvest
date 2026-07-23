# AGENTS.md — Guia para agentes automatizados

Este arquivo orienta agentes de IA e scripts automatizados que interagem com este repositório.

## O que é este projeto

Coleta massiva de metadados OAI-PMH de periódicos científicos brasileiros em plataformas OJS. Utiliza o pacote `ojs-scrape` e o dataset PKP Beacon v6 como fonte de URLs.

## Diretório de trabalho

Use a raiz do repositório como diretório de trabalho.

## Scripts disponíveis

### `scripts/harvest_complete.py` — Orquestrador da coleta completa

Executa as três fases em sequência, com resumabilidade e checkpoints:

1. **Fase 1 — Portais:** coleta por set (descobrir sets via ListSets, coletar cada set)
2. **Fase 2 — Isolados:** coleta integral (sem filtro de set)
3. **Fase 3 — Retry:** timeout 600s + `--no-verify-ssl` para falhas

```bash
# Coleta completa (todas as fases)
python3 scripts/harvest_complete.py --resume --verbose

# Apenas uma fase
python3 scripts/harvest_complete.py --phase 1 --resume -v

# Dry run (simular)
python3 scripts/harvest_complete.py --dry-run

# Com timeouts customizados
python3 scripts/harvest_complete.py --timeout-set 120 --timeout-iso 300 --timeout-retry 600
```

Parâmetros principais:
- `--phase N` — executar apenas a fase N (1, 2 ou 3)
- `--resume` — retomar a partir do checkpoint
- `--dry-run` — simular sem coletar
- `--timeout-set N` — timeout por set na Fase 1 (default: 120s)
- `--timeout-iso N` — timeout por isolado na Fase 2 (default: 300s)
- `--timeout-retry N` — timeout por retry na Fase 3 (default: 600s)
- `--delay N` — delay entre requisições (default: 1.0s)
- `--delay-usp N` — delay para USP e portais com rate limiting (default: 5.0s)
- `--skip-unresponsive` — pular 225 URLs não responsivas (default: True)

Saída: `data/raw/` (JSON por set/periódico) + `phase{N}_results.json` + `harvest_complete_checkpoint.json`

### `scripts/prepare_beacon_dataset.py` — Preparo do recorte brasileiro

Reproduz `data/processed/ojs_brazil_pkp_beacon.json` a partir da exportação tabular oficial do PKP Beacon v6.
O arquivo bruto global `data/raw/beacon.tab` não é versionado porque contém `admin_email` e dados globais não necessários.

```bash
python3 scripts/prepare_beacon_dataset.py --download
```

Ver `docs/data_provenance.md` para fonte, checksum e metodologia.

### `scripts/process_harvest.py` — Validação e consolidação pós-coleta

Consolida os JSONs brutos de `data/raw/` em saídas derivadas não versionadas.

```bash
python3 scripts/process_harvest.py --input-dir data/raw --output-dir data/derived
```

Regras centrais:
- fusão automática apenas por DOI, `oai_identifier` ou URL canônica;
- chave fraca de título, primeiro autor e ano gera candidatos para revisão, sem fusão automática;
- cada registro consolidado preserva `_provenance`.

Ver `docs/processing_pipeline.md`.

### Scripts legados

Scripts históricos das passadas amostrais e retries foram movidos para `scripts/legacy/`.
Eles servem para auditoria metodológica, não para iniciar novas coletas.

Ver `scripts/legacy/README.md`.

### Fonte de dados

`data/processed/ojs_brazil_pkp_beacon.json` — 6.086 periódicos brasileiros com metadados do PKP Beacon. Portais são identificados contando ocorrências de `oai_url`; não existe campo `n_journals`.

## Convenções

- **Dados brutos** em `data/raw/` — JSON individual por periódico ou set, com slug legível e hash estável da URL/set
- **Dados processados** em `data/processed/` — dataset filtrado, listas
- **Dados derivados** em `data/derived/` — consolidação local, não versionada
- **Logs** em `data/logs/` — logs de execução
- **Documentação** em `docs/` — metodologia, resultados, relatórios
- **Não coletar PDFs** — escopo é metadados apenas
- **Respeitar rate limiting** — delay mínimo de 1s entre requisições; 5-10s para portais com rate limiting agressivo (ex.: USP)

## Estratégia de coleta (ordem correta)

1. Portais → Fase 1 de `scripts/harvest_complete.py` (coleta por set primeiro)
2. Periódicos isolados → Fase 2 de `scripts/harvest_complete.py` (coleta integral)
3. Retry → Fase 3 de `scripts/harvest_complete.py` (SSL bypass + timeout 600s)
4. Portais agressivos → delay alto, madrugada

## Erros comuns

- **Timeout em portais**: usar coleta por set (Fase 1 do `harvest_complete.py`)
- **SSL (certificados expirados/self-signed)**: usar `--no-verify-ssl` (nativo no ojs-scrape desde PR #10)
- **HTTP 102**: aumentar timeout para 600s (Fase 3 do `harvest_complete.py`)
- **DNS inexistente**: não recuperável, registrar e skip
- **XML inválido**: ojs-scrape já faz limpeza; alguns casos inescapáveis
- **Rate limiting (USP)**: `harvest_complete.py` aplica delay 5s automaticamente para `revistas.usp.br`

Ver `docs/error_report.md` para análise completa.

## Ambiente

- Python 3.12+
- Dependências: `ojs-scrape` (ver `requirements.txt`)
- Os dados brutos estão em `.gitignore` (`data/raw/*`, `data/logs/*.log`)
- **A coleta completa não roda na VPS** — será executada em máquina do LABHDUFBA

## Git

- Branch: `main`
- Commits: mensagens em português, concisas
- Não commitar dados brutos (`.gitignore` já os exclui)