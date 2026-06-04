# Resultados da Coleta OAI-PMH — Amostra de Validação

**Período:** 2026-05-31 a 2026-06-04  
**Dataset fonte:** PKP Beacon v6 (6.086 OJS Brasil, 5.861 responsivos)  
**Scripts:** `scripts/harvest_batch.py` (P1), `scripts/harvest_by_set.py` (P2), `scripts/retry_ssl.py` (SSL)

---

## Resumo Consolidado

| Métrica | P1 (integral) | P2 (por set) | Retry SSL | Total |
|---------|---------------|---------------|-----------|-------|
| Targets tentados | 221 URLs | 2.361 sets (59 portais) | 29 URLs (37 targets) | — |
| ✅ Sucesso | 70 (32%) | 1.828 (77%) | 37 (100% conectados) | — |
| ⏱ Timeout | 63 (28%) | 307 (13%) | 0 | — |
| ❌ Erro | 88 (40%) | 226 (10%) | 22 (servidor) | — |
| **Registros coletados** | **48.298** | **599.684** | **54.948** | **702.930** |

| Métrica de disco | Valor |
|------------------|-------|
| Registros em disco | ~910.000 |
| Arquivos JSON | 2.100+ |
| Tamanho em disco | ~4 GB |
| Potencial do dataset PKP | 2.445.213 registros |
| Cobertura do potencial | **~37%** |

---

## Diagnóstico: portal vs. periódico isolado (Passada 1)

| Tipo | Tentados | Sucesso | Taxa |
|------|----------|---------|------|
| Periódicos isolados | 166 | 69 | **42%** |
| Portais multi-revista | 55 | 1 | **2%** |

Quase todo o sucesso da P1 vem de periódicos com instalação própria. A quase totalidade dos portais falha por timeout na coleta integral — confirmando a necessidade de coletar por set.

---

## Retry SSL — Etapa 1

29 URLs com erro SSL recuperadas via monkey-patch em `requests.Session.request`:

| Status | Qtd | Observação |
|--------|-----|------------|
| ✅ Sucesso | 37 | 6 já existiam, 31 novos |
| ❌ HTTP 500 (servidor) | 15 | Irrecuperável |
| ❌ OAI-PMH error | 5 | Sets vazios |
| ❌ SSL persistente | 1 | `portalgt.idp.edu.br` |
| ❌ XML inválido | 1 | `coffeescience.ufla.br` |

Top resultados: UFPE (23.246), Ufac (4.627), UNICENTRO (3.803), SPGG (3.316), UFRPE (3.258).

Detalhes em `docs/ssl_retry_results.md` e `docs/error_report.md`.

---

## Top 10 portais por volume (Passada 2)

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

## Estatísticas dos periódicos com sucesso (Passada 1)

- Média: 690 registros/periódico
- Mediana: 293 registros/periódico
- Mínimo: 5 registros
- Máximo: 4.596 registros

---

## Próximos passos

Detalhados em `docs/ROADMAP.md`.