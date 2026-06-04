# AGENTS.md — Guia para agentes automatizados

Este arquivo orienta agentes de IA e scripts automatizados que interagem com este repositório.

## O que é este projeto

Coleta massiva de metadados OAI-PMH de periódicos científicos brasileiros em plataformas OJS. Utiliza o pacote `ojs-scrape` e o dataset PKP Beacon v6 como fonte de URLs.

## Diretório de trabalho

```
/home/ebn/projetos/ojs-brazil-harvest
```

## Scripts disponíveis

### `scripts/harvest_batch.py` — Coleta integral (Passada 1)

Coleta periódicos sem filtro de set. Para periódicos isolados.

```bash
python3 scripts/harvest_batch.py \
  --sample 400 --seed 4 \
  --skip-unresponsive --resume \
  --timeout 180 --verbose
```

Parâmetros principais:
- `--sample N` — limitar a N URLs (remover para universo completo)
- `--seed N` — seed para amostragem aleatória
- `--skip-unresponsive` — pular 225 URLs não responsivas do dataset
- `--resume` — retomar a partir do último resultado, pulando URLs já coletadas
- `--timeout N` — timeout em segundos por URL
- `--verbose` —输出 detalhado

Saída: `data/raw/harvest_results_YYYYMMDD_HHMMSS.json` + arquivos JSON por periódico em `data/raw/`

### `scripts/harvest_by_set.py` — Coleta por set (Passada 2)

Coleta portais multi-revista set por set. A abordagem preferencial para portais.

```bash
python3 scripts/harvest_by_set.py \
  --timeout 120 --resume --verbose
```

Parâmetros principais:
- `--timeout N` — timeout por set (default: 120s)
- `--resume` — retomar a partir do progresso salvo
- `--verbose` —输出 detalhado
- `--dry-run` — apenas ListSets, sem coletar registros

Saída: `data/raw/harvest_by_set_results_YYYYMMDD_HHMMSS.json` + progresso em `data/raw/harvest_by_set_progress.json`

### Fonte de dados

`data/processed/ojs_brazil_pkp_beacon.json` — 6.086 periódicos brasileiros com metadados do PKP Beacon, incluindo `oai_url`, `n_journals`, `application_version`, `country_consolidated`.

## Convenções

- **Dados brutos** em `data/raw/` — JSON individual por periódico (slug do nome) ou por set (`slug__set_spec`)
- **Dados processados** em `data/processed/` — dataset filtrado, listas
- **Logs** em `data/logs/` — logs de execução
- **Documentação** em `docs/` — metodologia, resultados, relatórios
- **Não coletar PDFs** — escopo é metadados apenas
- **Respeitar rate limiting** — delay mínimo de 1s entre requisições; 5-10s para portais com rate limiting agressivo (ex.: USP)

## Estratégia de coleta (ordem correta)

1. Portais → `harvest_by_set.py` (coleta por set primeiro)
2. Periódicos isolados → `harvest_batch.py` (coleta integral)
3. Retry → SSL bypass + timeout 600s
4. Portais agressivos → delay alto, madrugada

## Erros comuns

- **Timeout em portais**: usar coleta por set
- **SSL**: contornar com `PYTHONHTTPSVERIFY=0` ou patch no ojs-scrape
- **HTTP 102**: aumentar timeout para 600s
- **DNS inexistente**: não recuperável, registrar e skip
- **XML inválido**: ojs-scrape já faz limpeza; alguns casos inescapáveis

Ver `docs/error_report.md` para análise completa.

## Ambiente

- Python 3.12+
- Dependências: `ojs-scrape` (ver `requirements.txt`)
- Os dados brutos estão em `.gitignore` (`data/raw/*.json`, `data/logs/*.log`)
- **A coleta completa não roda na VPS** — será executada em máquina do LABHDUFBA

## Git

- Branch: `main`
- Commits: mensagens em português, concisas
- Não commitar dados brutos (`.gitignore` já os exclui)