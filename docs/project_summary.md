# Projeto OJS Brazil Harvest — Mapeamento de Periódicos Científicos Brasileiros via OAI-PMH

**Laboratório LABHDUFBA — Universidade Federal da Bahia**  
**Eric Brasil Nepomuceno**  
**Atualizado:** Junho de 2026

---

## 1. Apresentação

O projeto **OJS Brazil Harvest** realiza a coleta sistemática de metadados de periódicos científicos brasileiros hospedados em plataformas OJS (Open Journal Systems), utilizando o protocolo OAI-PMH. O objetivo é construir um dataset aberto e consolidado da produção científica publicada em periódicos OJS no Brasil, viabilizando análises bibliométricas, estudos de acesso aberto e diagnósticos da infraestrutura editorial nacional.

---

## 2. Fonte dos dados

**Dataset PKP Beacon v6** (Khanna et al., 2025 — Harvard Dataverse, CC0)

- 87.170 instalações OJS/OMP/OPS em todo o mundo
- Filtro: `country_consolidated == "BR"` e `application == "ojs"`
- Resultado: **6.086 periódicos brasileiros**, dos quais **5.861** com endpoint OAI-PMH responsivo
- Potencial estimado: **2.445.213 registros** de artigos

A estrutura do universo revela uma característica importante: **4.422 periódicos (75%) estão hospedados em 538 portais multi-revista** (SEER/portal institucional), compartilhando o mesmo domínio e endpoint OAI-PMH. Apenas 1.439 periódicos possuem instalação OJS própria e independente. Essa concentração em portais é determinante para a estratégia de coleta.

---

## 3. Ferramenta de coleta: ojs-scrape

A coleta utiliza o pacote Python [**ojs-scrape**](https://pypi.org/project/ojs-scrape/) (v0.1.1), que implementa:

- Protocolo OAI-PMH completo — `ListRecords` com paginação via `resumptionToken`
- Tratamento automático de caracteres de controle XML inválidos (comum em OJS 3.1.x/3.2.x)
- Filtro por data de publicação (parâmetro `from`/`until`)
- Coleta seletiva por set (`--set`), que permite isolar revistas individuais dentro de portais
- Exportação em JSON, CSV e BibTeX

O `ojs-scrape` é chamado via linha de comando como subprocesso, permitindo controle de timeout e monitoramento individual de cada coleta.

---

## 4. Estratégia de coleta

### Problema central

O tamanho dos repositórios OAI-PMH nos portais multi-revista gera um problema central: o endpoint agregado (`/index/oai`) lista **todos** os registros de **todas** as revistas do portal numa única resposta. Portais como o da USP, UFES ou SBC possuem mais de 1.000 sets — a resposta OAI-PMH pode exceder dezenas de milhares de registros, causando timeout do servidor.

### Estratégia original (validada e descartada)

A primeira abordagem testou duas passadas sequenciais:
1. Passada 1 — coleta integral (sem set): funciona para isolados, falha para quase todos os portais (98% de falha)
2. Passada 2 — coleta por set: recupera os portais após timeout

**Problema:** a Passada 1 desperdiça ~240s em cada portal que vai falhar de qualquer forma.

### Estratégia revisada (para o universo completo)

Com base nos resultados da amostra, a ordem ótima é:

1. **Portais → coleta por set PRIMEIRO** — descobrir sets via `ListSets`, coletar cada revista individualmente
2. **Periódicos isolados → coleta integral** — funciona bem (42% de sucesso na amostra)
3. **Retry com SSL bypass e timeout estendido (600s)** — segunda rodada
4. **Portais com rate limiting agressivo (ex.: USP) → abordagem dedicada** — delay alto, madrugada, possível proxy

### O processo de coleta por set

1. **Descobrir os sets disponíveis** via `ListSets` (com paginação por `resumptionToken`)
2. **Filtrar apenas sets de nível superior** — sets com `:` no setSpec (ex.: `bjos:ART`, `cel:EDI`) são sub-seções editoriais, não revistas. Apenas sets como `bjos`, `cel`, `cadpagu` correspondem a revistas individuais.
3. **Coletar cada set individualmente** com `ojs-scrape --set <set_spec>`, timeout 120s por set
4. Cada set gera um arquivo JSON separado: `portal_de_periodicos_da_usp__revista_de_saude_publica.json`

---

## 5. Resultados da amostra de validação

Coletas amostrais com diferentes seeds sobre as 5.861 URLs responsivas, seguidas de coleta por set nos portais com timeout.

### Consolidado

| Métrica | Passada 1 (integral) | Passada 2 (por set) |
|---------|---------------------|---------------------|
| Targets tentados | 221 URLs | 2.361 sets (59 portais) |
| ✅ Sucesso | 70 (32%) | 1.828 (77%) |
| ⏱ Timeout | 63 (28%) | 307 (13%) |
| ❌ Erro | 88 (40%) | 226 (10%) |
| **Registros coletados** | **48.298** | **599.684** |

| Métrica consolidada | Valor |
|---------------------|-------|
| Registros em disco | 856.085 |
| Arquivos JSON | 2.097 |
| Tamanho em disco | 3,5 GB |
| Cobertura do potencial (2,4M) | **35%** |

### Diagnóstico: portal vs. periódico isolado

| Tipo | Tentados | Sucesso | Taxa |
|------|----------|---------|------|
| Periódicos isolados | 166 | 69 | **42%** |
| Portais multi-revista | 55 | 1 | **2%** |

Quase todo o sucesso da Passada 1 vem de periódicos com instalação própria. A quase totalidade dos portais falha por timeout na coleta integral — confirmando a necessidade de coletar por set.

### Tipos de erro consolidados

| Tipo | Qtd | Recuperável? |
|------|-----|-------------|
| HTTP 102 Processing | 34 | Sim — coletar por set ou timeout 600s |
| SSL (certificado inválido) | 17 | Sim — bypass SSL |
| ConnectTimeout | 14 | Parcialmente — pode voltar depois |
| ConnectionError/DNS | 14 | Não — domínio inexistente |
| XML/Parse | 7 | Parcialmente — ojs-scrape já limpa alguns |
| USP (rate limiting) | 194 sets | Difícil — delay alto, madrugada |

Detalhamento completo em `docs/error_report.md`.

---

## 6. Expectativa final

### Escala do universo

| Métrica | Valor |
|---------|-------|
| Periódicos com endpoint responsivo | 5.861 |
| URLs OAI únicas | 1.977 |
| Portais multi-revista | 538 |
| Periódicos isolados | 1.439 |
| Potencial de registros | ~2,4 milhões |

### Estimativa de coleta completa

Com a estratégia revisada (set primeiro, isolados depois, retry em seguida):

- **Portais por set** (538 portais, ~94% de sucesso por set): ~1.800.000 registros
- **Isolados** (1.439, ~42% de sucesso): ~300.000 registros
- **SSL bypass + retry timeout 600s**: +80.000-175.000 registros
- **Total estimado**: **1,8 — 2,2 milhões de registros** (75-90% do potencial)

### Produtos esperados

1. **Dataset consolidado** — JSON/CSV com metadados deduplicados de ~2 milhões de artigos, com ISSNs, DOIs e datas de publicação
2. **Relatório de infraestrutura** — diagnóstico dos periódicos OJS brasileiros: versões, certificados SSL, configuração OAI-PMH, disponibilidade
3. **Dataset de portais** — mapeamento dos 538 portais multi-revista e suas revistas constituintes
4. **Documentação metodológica** — protocolo reprodutível de coleta OAI-PMH em larga escala

---

## Referências

- Khanna, S.; Raoni, J.; Smecher, A.; Alperin, J.P.; Ball, J.; Willinsky, J. (2025). "Details of publications using software by the Public Knowledge Project". Harvard Dataverse, V6. DOI: [10.7910/DVN/OCZNVY](https://doi.org/10.7910/DVN/OCZNVY)
- Khanna, S., Ball, J., Alperin, J. P., & Willinsky, J. (2022). Recalibrating the Scope of Scholarly Publishing. *Quantitative Science Studies*. DOI: [10.1162/qss_a_00228](https://doi.org/10.1162/qss_a_00228)
- [ojs-scrape](https://pypi.org/project/ojs-scrape/) — CLI para coleta de metadados via OAI-PMH
- Open Archives Initiative. *The Open Archives Initiative Protocol for Metadata Harvesting*. [oai-pmh.com](https://www.openarchives.org/OAI/openarchivesprotocol.html)