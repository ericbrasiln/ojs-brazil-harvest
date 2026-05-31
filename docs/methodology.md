# Metodologia de Coleta — OJS Brazil Harvest

## Decisões de Design

### 1. Fonte: PKP Beacon v6

Dataset: [Khanna et al., 2025 — Harvard Dataverse](https://doi.org/10.7910/DVN/OCZNVY), licença CC0.

- **Total original:** 87.170 instalações OJS/OMP/OPS
- **Filtro:** `country_consolidated == "BR"` e `application == "ojs"`
- **Resultado:** 6.086 periódicos, 5.861 com endpoint OAI-PMH responsivo

### 2. Estratégia de Coleta: duas passadas

**Problema:** 74% dos periódicos (4.532) estão em 573 portais multi-revista (SEER/portal institucional). Coletar todos os registros de um portal de uma vez causa timeouts (até 1.284 sets num portal).

**Passada 1 — Coleta integral:**
- Para cada URL OAI, executa `ojs-scrape` sem filtro de set
- Timeout de 300s por periódico
- Periódicos pequenos e médios (até ~500 registros) completam normalmente

**Passada 2 — Coleta por set (portais com timeout):**
- Portais que falharam com timeout na Passada 1 são reprocessados
- Primeiro descobre os sets disponíveis via `ListSets`
- Depois coleta set por set, evitando respostas OAI-PMH gigantes

### 3. Ferramenta: ojs-scrape CLI

Usamos [ojs-scrape](https://pypi.org/project/ojs-scrape/) v0.1.1 como motor de coleta, que implementa:

- Protocolo OAI-PMH (`ListRecords` com paginação via `resumptionToken`)
- Tratamento de caracteres de controle XML inválidos (comum em OJS 3.1.x/3.2.x)
- Filtro local por data de publicação (OAI `from`/`until` filtram por datestamp, não por data de publicação)
- Exportação em JSON, CSV e BibTeX

### 4. Parâmetros de Coleta

| Parâmetro | Valor | Justificativa |
|-----------|-------|---------------|
| `--from` | 2000 | Capturar toda a produção dos periódicos |
| `--until` | ano atual | Atualizar até o presente |
| `--timeout` | 300s | 5 min por periódico (portais grandes são lentos) |
| `--delay` | 1.0s | Respeitar rate limiting dos servidores |
| `--format` | json | Formato nativo — CSV/BibTeX podem ser gerados depois |
| PDFs | **não coletados** | Escopo é metadados apenas |

### 5. Tratamento de Erros

Baseado no teste-piloto (20 periódicos, 7 versões do OJS):

| Tipo de erro | Frequência | Tratamento |
|--------------|------------|------------|
| Timeout (>300s) | ~50% (portais) | Passar para coleta por set |
| ConnectTimeout | ~5% | Registrar, skip |
| 403 Forbidden | ~5% | Registrar, skip |
| 500 Internal Server Error | ~10% | Registrar, skip |
| SSL cert expirado | ~5% | Registrar, skip |
| badVerb (OAI mal configurado) | ~5% | Registrar, skip |
| XML chars inválidos | ~10% | ojs-scrape trata automaticamente |

**Não retry automático** para erros não transitórios (403, 500, badVerb). Retry com backoff seria útil para timeouts, mas optamos por resolver via coleta por set na segunda passada.

### 6. Versão do OJS: não é fator determinante

O teste-piloto mostrou que a versão do OJS (2.x a 3.5.x) não é o fator principal de sucesso/falha. Sucessos: 2.x, 3.3.x, 3.5.x. Falhas em todas as versões. Os fatores reais são:

1. **Tamanho do repositório** — portais com 1.000+ sets demoram demais
2. **Infraestrutura do servidor** — timeouts, SSL, bloqueios
3. **Configuração OAI-PMH** — badVerb, chars inválidos

### 7. Estrutura de Saída

```
data/raw/
├── portal_de_periodicos_da_ufrj.json        # Portal inteiro (se completou)
├── portal_de_periodicos_da_ufrj__art.json   # Set individual (se coleta por set)
├── harvest_results_20260531_120000.json      # Log consolidado da coleta
data/logs/
├── harvest_20260531_120000.log               # Log detalhado
```

Nomes de arquivo: `{slug_do_nome}__{set_spec}.json` para sets individuais, `{slug_do_nome}.json` para coletas integrais.

---

## Referências

- Khanna, S.; Raoni, J.; Smecher, A.; Alperin, J.P.; Ball, J.; Willinsky, J. (2025). "Details of publications using software by the Public Knowledge Project". Harvard Dataverse, V6. DOI: [10.7910/DVN/OCZNVY](https://doi.org/10.7910/DVN/OCZNVY)
- Khanna, S., Ball, J., Alperin, J. P., & Willinsky, J. (2022). Recalibrating the Scope of Scholarly Publishing. *Quantitative Science Studies*. DOI: [10.1162/qss_a_00228](https://doi.org/10.1162/qss_a_00228)
- [ojs-scrape](https://pypi.org/project/ojs-scrape/) — CLI para coleta de metadados via OAI-PMH