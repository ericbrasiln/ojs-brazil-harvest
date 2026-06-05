# Resultados da Coleta OAI-PMH — Amostra de Validação

**Período:** 2026-05-31 a 2026-06-05  
**Dataset fonte:** PKP Beacon v6 (6.086 OJS Brasil, 5.861 responsivos)  
**Scripts:** `harvest_batch.py`, `harvest_by_set.py`, `retry_ssl.py`, `retry_isolated.py`, `retry_portals_by_set.py`

---

## Resumo Consolidado

| Fase | Registros | Detalhes |
|------|-----------|---------|
| P1 (integral) | 48.298 | 70 URLs OK de 221 |
| P2 (por set) | 599.684 | 1.828 sets OK de 2.365 |
| Etapa 1 — SSL | 54.948 | 29 URLs antes inacessíveis |
| Etapa 2a — Isolados | 8.589 | 1 URL (UEG) |
| Etapa 2b — Portais | 453.884 | 511 sets, 1.946 skip (sem duplicação) |
| Etapa 3 — P2 errors | 4.342 | 4 sets OK, 138 noRecordsMatch, 79 skip |
| **Total bruto** | **~1.169K** | |
| **Registros únicos** | **~925K+** | 18% sobreposição entre sets |

| Métrica de disco | Valor |
|------------------|-------|
| Arquivos JSON | 2.100+ |
| Tamanho em disco | ~4 GB |
| Potencial PKP Beacon | 2.445.213 |
| Cobertura | **~38%** |

---

## Diagnóstico: portal vs. periódico isolado (P1)

| Tipo | Tentados | Sucesso | Taxa |
|------|----------|---------|------|
| Periódicos isolados | 166 | 69 | **42%** |
| Portais multi-revista | 55 | 1 | **2%** |

---

## Retry SSL — Etapa 1

29 URLs com erro SSL recuperadas via monkey-patch `requests.Session.request` com `verify=False`:

| Status | Qtd | Observação |
|--------|-----|------------|
| ✅ Sucesso | 37 | 6 já existiam, 31 novos |
| ❌ HTTP 500 | 15 | Irrecuperável |
| ❌ OAI-PMH error | 5 | Sets vazios |
| ❌ SSL persistente | 1 | `portalgt.idp.edu.br` |
| ❌ XML inválido | 1 | `coffeescience.ufla.br` |

Bug fix: `from_date="2000-01-01"` (não `"2000"`). Issue: [ojs-scrape#9](https://github.com/ericbrasiln/ojs-scrape/issues/9)

---

## Retry Isolados — Etapa 2a

36 URLs isoladas com erro (não-SSL, não-portais). Probe rápido (15s) + timeout 600s.

| Status | Qtd |
|--------|-----|
| ✅ Alive | 19 |
| ❌ Mortas/bloqueadas | 17 |
| ✅ Harvest OK | 1 (UEG — 8.589 registros) |
| ❌ Harvest erro | 21 |

⚠️ **Lição crítica:** NÃO coletar portais integralmente — duplica dados da P2. Portais = retry por set.

---

## Retry Portais — Etapa 2b

77 portais com erro na P1/P2. Coleta por set com deduplicação.

| Métrica | Valor |
|---------|-------|
| Portais processados | 62 (15 ListSets falhou) |
| Sets OK | 511 |
| Sets com erro | 215 |
| Sets skip (já OK P2) | 1.946 |
| **Registros novos** | **453.884** |

---

## Top 10 portais por volume (P2)

| Portal | Sets OK | Registros |
|--------|---------|-----------|
| Portal de Conteúdo da SBC | 177/188 | 34.498 |
| SEER UFRGS | 79/99 | 38.508 |
| Biblioteca Digital Periódicos UFPR | 65/79 | 21.145 |
| Portal de Periódicos da UFPB | 80/104 | 20.415 |
| Periódicos da UFES | 70/100 | 18.549 |
| Periódicos da UFF | 64/72 | 19.422 |
| Portal de Periódicos UFSC | 39/50 | 24.523 |
| Portal de Periódicos UFPE | 62/70 | 12.949 |
| Portal de Periódicos da UFU | 21/47 | 4.947 |
| Portal de Periódicos Unicamp | 33/33 | 38.104 |

---

## Estatísticas dos periódicos com sucesso (P1)

- Média: 690 registros/periódico
- Mediana: 293 registros/periódico
- Mínimo: 5 registros
- Máximo: 4.596 registros