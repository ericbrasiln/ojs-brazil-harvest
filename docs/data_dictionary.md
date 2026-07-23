# Dicionário de dados

Este dicionário descreve os principais arquivos produzidos pelo projeto.

## `data/processed/ojs_brazil_pkp_beacon.json`

Recorte brasileiro do PKP Beacon v6.

| Campo | Tipo | Descrição |
|---|---:|---|
| `oai_url` | string | Endpoint OAI-PMH da instalação OJS ou portal. |
| `base_url` | string | URL base derivada do endpoint OAI-PMH. |
| `repository_name` | string | Nome do repositório OAI informado pelo endpoint. |
| `context_name` | string | Nome do periódico ou contexto no PKP Beacon. |
| `version` | string | Versão declarada do OJS. |
| `issn` | string | ISSN(s) conhecidos. Múltiplos ISSNs são separados por ponto e vírgula. |
| `total_record_count` | integer | Total de registros estimado pelo PKP Beacon. |
| `unresponsive_endpoint` | boolean | Indica endpoint OAI-PMH não responsivo no Beacon. |
| `unresponsive_context` | boolean | Indica contexto não responsivo no Beacon. |
| `earliest_datestamp` | datetime/string | Primeiro datestamp OAI-PMH observado pelo Beacon. |
| `last_oai_response` | datetime/string | Última resposta OAI-PMH observada pelo Beacon. |
| `record_count_2020`…`record_count_2025` | integer | Contagens anuais estimadas pelo Beacon. |
| `country_consolidated` | string | País consolidado. Filtrado para `BR`. |
| `region` | string | Região geográfica no Beacon. |
| `set_spec` | string | Set OAI-PMH associado ao periódico/contexto quando disponível. |

## `data/derived/articles.jsonl`

Arquivo gerado por `scripts/process_harvest.py`.
Não é versionado por padrão.

Cada linha é um registro JSON de artigo.
Os campos originais vêm do `ojs-scrape`.
O pipeline acrescenta `_provenance`.

Quando há duplicata por identificador forte, os campos do primeiro registro válido são mantidos.
Os campos de ocorrências posteriores não são combinados; apenas suas origens são acrescentadas a `_provenance`.

| Campo | Tipo | Descrição |
|---|---:|---|
| `oai_identifier` | string | Identificador OAI-PMH do registro. |
| `article_id` | integer/string | Identificador interno do artigo no OJS quando disponível. |
| `url` | string | URL pública do artigo. |
| `datestamp` | datetime/string | Datestamp OAI-PMH. |
| `title` | string | Título do artigo. |
| `subtitle` | string | Subtítulo, quando disponível. |
| `creators` | list[string] | Autores ou criadores informados pelo OAI-PMH. |
| `subjects` | list[string] | Assuntos e palavras-chave. |
| `descriptions` | list[string] | Resumos ou descrições. |
| `publishers` | list[string] | Editores ou instituições publicadoras. |
| `contributors` | list[string] | Colaboradores. |
| `dates` | list[string] | Datas de publicação ou disponibilidade. |
| `identifiers` | list[string] | Identificadores adicionais, incluindo DOI ou URL. |
| `types` | list[string] | Tipos Dublin Core/OAI. |
| `formats` | list[string] | Formatos declarados. |
| `sources` | list[string] | Fonte, volume, número, páginas e ISSN quando declarados. |
| `languages` | list[string] | Idiomas declarados. |
| `rights` | list[string] | Declarações de direitos do periódico/artigo. |
| `doi` | string | DOI extraído ou normalizado pelo `ojs-scrape`, quando disponível. |
| `pages` | string | Intervalo de páginas. |
| `resumo` | string | Resumo principal extraído pelo `ojs-scrape`. |
| `palavras_chave` | list[string] | Palavras-chave normalizadas pelo `ojs-scrape`. |
| `set_spec` | string | Set OAI-PMH usado na coleta. |
| `set_specs` | list[string] | Sets OAI-PMH associados ao registro. |
| `set_name` | string | Nome do set quando disponível. |
| `issue_id` | integer/string | ID interno da edição no OJS quando disponível. |
| `issue_number` | string | Número da edição. |
| `section` | string | Seção do periódico. |
| `pdf_url` | string | URL de PDF declarada pelo OJS. PDFs não são baixados. |
| `deleted` | boolean | Indica registro OAI-PMH marcado como deletado. |
| `_provenance` | list[object] | Ocorrências de origem do registro consolidado. |

### `_provenance`

| Campo | Tipo | Descrição |
|---|---:|---|
| `source_file` | string | Arquivo bruto em `data/raw/`. |
| `source_index` | integer | Posição do registro no arquivo bruto. |
| `source_sha256` | string | SHA-256 do arquivo bruto. |

## `data/derived/articles.csv`

Versão tabular reduzida de `articles.jsonl`.
Listas são serializadas com ` | `.
Use `articles.jsonl` quando precisar preservar todos os campos e estruturas aninhadas.

## Arquivos de auditoria

| Arquivo | Descrição |
|---|---|
| `data/derived/manifest.json` | Manifesto da execução, checksums e resumo. |
| `data/derived/validation_report.json` | Registros inválidos e alertas. |
| `data/derived/duplicate_decisions.csv` | Fusões automáticas por DOI, OAI identifier ou URL. |
| `data/derived/duplicate_candidates.json` | Candidatos por chave fraca para revisão humana. |
