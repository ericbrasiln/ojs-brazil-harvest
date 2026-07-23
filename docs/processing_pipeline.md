# Validação e consolidação pós-coleta

Este documento descreve a etapa de pós-coleta do OJS Brazil Harvest.

## Entrada

A entrada são arquivos JSON brutos em `data/raw/`, produzidos por `scripts/harvest_complete.py`.
Arquivos de controle não são processados como artigos:

- `phase*_results.json`
- `harvest_complete_checkpoint.json`
- `harvest_*`
- `retry_*`
- `probe_*`

## Comando

```bash
python3 scripts/process_harvest.py \
  --input-dir data/raw \
  --output-dir data/derived
```

## Saídas

`data/derived/` não é versionado por padrão.

| Arquivo | Função |
|---|---|
| `articles.jsonl` | Registros consolidados, um JSON por linha, com campo `_provenance` |
| `articles.csv` | Versão tabular reduzida para análise exploratória |
| `duplicate_decisions.csv` | Decisões automáticas de fusão por identificador forte |
| `duplicate_candidates.json` | Possíveis duplicatas por chave fraca, sem fusão automática |
| `validation_report.json` | Arquivos inválidos, registros inválidos e alertas |
| `manifest.json` | Manifesto da execução, checksums das entradas e resumo |

## Deduplicação

A fusão automática usa apenas identificadores fortes:

1. DOI normalizado;
2. identificador OAI (`oai_identifier`);
3. URL canônica.

Quando dois registros compartilham qualquer identificador forte, o primeiro registro válido em ordem lexicográfica de arquivo é mantido.
As demais ocorrências são anexadas ao campo `_provenance`.
A decisão é registrada em `duplicate_decisions.csv`.

O pipeline não combina campos entre duplicatas.
O conteúdo do primeiro registro é mantido; o conteúdo das ocorrências posteriores é descartado, preservando-se apenas sua proveniência.

A chave fraca `título normalizado + primeiro autor + ano` **não funde registros automaticamente**.
Ela serve apenas para gerar `duplicate_candidates.json` para revisão humana.

## Validação

Um registro é inválido se:

- não é objeto JSON;
- não tem identidade forte nem título.

Alertas não bloqueantes são contabilizados quando faltam:

- título;
- criadores;
- data de publicação.

Na execução completa de validação registrada em 22 de julho de 2026, nenhum registro acionou o alerta de data ausente.

## Proveniência

Cada registro consolidado recebe `_provenance`, lista de ocorrências com:

- `source_file`;
- `source_index`;
- `source_sha256`.

Essa estrutura permite recuperar a origem de cada linha consolidada sem apagar a variação dos arquivos brutos.

## Limites metodológicos

- Registros sem DOI, sem OAI identifier e sem URL podem ser mantidos como únicos se tiverem título.
- Similaridade textual não é usada para fusão automática.
- Variações de autores e títulos exigem revisão humana.
- Direitos autorais e licenças variam por periódico. Os campos `rights` são preservados, mas não harmonizados nesta etapa.
