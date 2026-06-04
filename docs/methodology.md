# Metodologia de Coleta — OJS Brazil Harvest

## Decisões de Design

### 1. Fonte: PKP Beacon v6

Dataset: [Khanna et al., 2025 — Harvard Dataverse](https://doi.org/10.7910/DVN/OCZNVY), licença CC0.

- **Total original:** 87.170 instalações OJS/OMP/OPS
- **Filtro:** `country_consolidated == "BR"` e `application == "ojs"`
- **Resultado:** 6.086 periódicos, 5.861 com endpoint OAI-PMH responsivo
- **Registros potenciais:** 2.445.213

Arquivo processado: `data/processed/ojs_brazil_pkp_beacon.json` (1.977 OAI URLs únicas: 538 portais + 1.439 isolados)

### 2. Estratégia de Coleta

**Problema:** 75% dos periódicos (4.422) estão em 538 portais multi-revista (SEER/portal institucional). Coletar todos os registros de um portal de uma vez causa timeouts — portais como USP possuem 1.000+ sets.

**Estratégia revisada** (com base nos resultados da amostra):

#### Fase 1 — Portais: coleta por set

Para cada portal (URL com `n_journals > 1`):

1. Descobrir sets via `ListSets` (com paginação por `resumptionToken`)
2. Filtrar apenas sets de nível superior (sem `:` no setSpec — `bjos:ART` é sub-seção, `bjos` é revista)
3. Coletar cada set individualmente com `ojs-scrape --set <set_spec>`
4. Timeout 120s por set, delay 1.0s entre requisições
5. Resultados: um arquivo JSON por set

**Justificativa:** Na amostra, a coleta integral de portais teve 98% de falha. A coleta por set teve 77% de sucesso e rendeu 12x mais registros.

#### Fase 2 — Periódicos isolados: coleta integral

Para cada periódico com instalação própria (`n_journals == 1`):

- Executar `ojs-scrape` sem filtro de set
- Timeout 300s por periódico
- Sucesso esperado: ~42% (baseado na amostra)

#### Fase 3 — Retry

- SSL bypass para 17 URLs com certificado inválido
- Timeout 600s para HTTP 102 e timeouts previos
- Delay 2s para sets que falharam na Fase 1
- Portais com rate limiting agressivo (ex.: USP): delay 5-10s, horário de madrugada

### 3. Ferramenta: ojs-scrape CLI

Usamos [ojs-scrape](https://pypi.org/project/ojs-scrape/) v0.1.1 como motor de coleta, que implementa:

- Protocolo OAI-PMH (`ListRecords` com paginação via `resumptionToken`)
- Tratamento de caracteres de controle XML inválidos (comum em OJS 3.1.x/3.2.x)
- Filtro local por data de publicação (OAI `from`/`until` filtram por datestamp, não por data de publicação)
- Exportação em JSON, CSV e BibTeX

### 4. Parâmetros de Coleta

| Parâmetro | Valor (portais) | Valor (isolados) | Justificativa |
|-----------|-----------------|-------------------|---------------|
| `--from` | 2000 | 2000 | Capturar toda a produção |
| `--until` | ano atual | ano atual | Atualizar até o presente |
| `--timeout` | 120s por set | 300s por URL | Sets são menores; isolados precisam de mais tempo |
| `--delay` | 1.0s (5-10s para USP) | 1.0s | Respeitar rate limiting |
| `--format` | json | json | CSV/BibTeX podem ser gerados depois |
| `--set` | sim (por set) | não | Sets apenas para portais |
| PDFs | **não coletados** | **não coletados** | Escopo é metadados apenas |

### 5. Tratamento de Erros

Baseado nos resultados da amostra (221 URLs + 2.361 sets):

| Tipo de erro | Frequência | Tratamento |
|--------------|-----------|------------|
| Timeout em portais | 98% dos portais na coleta integral | Coletar por set (Fase 1) |
| Timeout em isolados | ~14% | Retry com timeout 600s (Fase 3) |
| HTTP 102 Processing | 15% (34/221) | Coletar por set ou timeout 600s |
| SSL cert expirado/inválido | 8% (17/221) | Bypass SSL (Fase 3) |
| ConnectTimeout | 6% (14/221) | Retry depois; registrar |
| ConnectionError/DNS | 6% (14/221) | Registrar, skip (domínio morto) |
| XML chars inválidos/Parse | 3% (7/221) | ojs-scrape trata automaticamente; alguns inescapáveis |
| Rate limiting agressivo (USP) | 1 portal, 194 sets | Abordagem dedicada: delay alto, madrugada |

**Não retry automático** para erros não transitórios (403, 500, DNS inexistente). Detalhamento completo em `docs/error_report.md`.

### 6. Versão do OJS: não é fator determinante

O teste-piloto mostrou que a versão do OJS (2.x a 3.5.x) não é o fator principal de sucesso/falha. Os fatores reais são:

1. **Tamanho do repositório** — portais com 1.000+ sets demoram demais na coleta integral
2. **Infraestrutura do servidor** — timeouts, SSL, bloqueios
3. **Configuração OAI-PMH** — badVerb, chars inválidos

### 7. Estrutura de Saída

```
data/raw/
├── portal_de_periodicos_da_ufrj__art.json     # Set individual (coleta por set)
├── portal_de_periodicos_da_ufrj__edu.json
├── revista_afroasia.json                       # Periódico isolado (coleta integral)
├── harvest_results_YYYYMMDD_HHMMSS.json       # Log consolidado da P1
├── harvest_by_set_results_YYYYMMDD_HHMMSS.json # Log consolidado da P2
├── harvest_by_set_progress.json               # Progresso da coleta por set
data/logs/
├── harvest_YYYYMMDD_HHMMSS.log                # Log detalhado
data/processed/
├── ojs_brazil_pkp_beacon.json                  # Dataset filtrado do PKP Beacon
├── ojs_brazil_responsive_urls.txt              # Lista de URLs responsivas
```

Nomes de arquivo: `{slug_do_nome}__{set_spec}.json` para sets, `{slug_do_nome}.json` para coletas integrais. O slug é derivado do `repositoryName` (minúsculas, espaços → underscores, caracteres especiais removidos).

---

## Referências

- Khanna, S.; Raoni, J.; Smecher, A.; Alperin, J.P.; Ball, J.; Willinsky, J. (2025). "Details of publications using software by the Public Knowledge Project". Harvard Dataverse, V6. DOI: [10.7910/DVN/OCZNVY](https://doi.org/10.7910/DVN/OCZNVY)
- Khanna, S., Ball, J., Alperin, J. P., & Willinsky, J. (2022). Recalibrating the Scope of Scholarly Publishing. *Quantitative Science Studies*. DOI: [10.1162/qss_a_00228](https://doi.org/10.1162/qss_a_00228)
- [ojs-scrape](https://pypi.org/project/ojs-scrape/) — CLI para coleta de metadados via OAI-PMH