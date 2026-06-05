# Plano de Ação — Retry de Erros da Amostra

**Branch:** `fix/retry-errors`  
**Objetivo:** Recuperar o máximo de registros dos targets que falharam na amostra, testando as estratégias antes de escalar para o universo completo.

---

## Visão geral dos 684 problemas

| Categoria | Qtd | Prioridade | Ganho estimado |
|-----------|-----|------------|-----------------|
| P1 isolados: SSL | 29 | ✅ Resolvido | +54.948 registros |
| P1 isolados: timeout/HTTP 102 | 36 | ✅ Resolvido | +8.589 (1 OK) |
| P1 portais com erro | 63 | ✅ Resolvido | +453.884 (511 sets) |
| P2 sets: erro (226) | 226 | Média | +20K-40K |
| P2 sets: timeout não-USP (113) | 113 | Média | +10K-30K |
| P2 sets: USP timeout (194) | 194 | Baixa | +50K-100K (difícil) |
| DNS/ConnectionError | 14 | Ignorar | 0 |
| XML/Parse | 7 | Baixa | incerto |

---

## Etapa 1 — SSL bypass ✅ CONCLUÍDA

**Resultado:** 54.948 registros de 37 targets com sucesso (27/29 URLs com SSL acessíveis)

**Lições:**
- `requests.Session.send` patch NÃO funciona — usar `requests.Session.request`
- `from_date="2000"` causa `badArgument` — usar `from_date="2000-01-01"`
- Issue aberta: [ojs-scrape#9](https://github.com/ericbrasiln/ojs-scrape/issues/9)

---

## Etapa 2a — Retry de Isolados ✅ CONCLUÍDA

**Estratégia:** probe rápido (15s) + harvest com timeout 600s, **apenas periódicos isolados**

**Resultado:**

| Métrica | Valor |
|---------|-------|
| URLs isoladas com erro | 36 |
| Probe alive | 19 |
| Probe mortas/bloqueadas | 17 |
| Harvest OK | 1 (UEG — 8.589 registros) |
| Harvest erro | 21 (403, 500, 400, 404, timeout) |

**⚠️ Lição crítica:** NÃO coletar portais integralmente — duplica dados da P2. Portais devem ser retried por set.

**Script:** `scripts/retry_isolated.py`

---

## Etapa 2b — Retry de Portais por Set ✅ CONCLUÍDA

**Estratégia:** descobre sets via ListSets, pula sets já OK na P2, retry apenas em sets com erro ou novos.

**Resultado:**

| Métrica | Valor |
|---------|-------|
| Portais processados | 62 (15 ListSets falhou) |
| Sets OK | 511 |
| Sets com erro | 215 |
| Sets skip (já OK na P2) | 1.946 |
| **Registros novos** | **453.884** |

**Lições:**
- Deduplicação com P2 funciona: 1.946 sets pulados, zero duplicação
- 15 portais com ListSets bloqueado (403, DNS, servidor morto)
- 215 sets com erro (500, timeout, XML inválido)

**Script:** `scripts/retry_portals_by_set.py`

---

## Etapa 3 — Retry P2 sets com erro e timeout (pendente)

**O que fazer:**
- Extrair os 226 sets com erro e 113 com timeout (excluindo USP)
- Executar `harvest_by_set.py` com `--timeout 300 --delay 2` apenas nesses sets
- Implementar filtragem de sets específicos (não reprocessar os que já deram OK)

---

## Etapa 4 — USP dedicado (194 sets)

**O que fazer:**
- Delay 5-10s entre sets, agendar para madrugada
- Se rate limiting persistir, investigar por IP ou user-agent

---

## Etapa 5 — Investigar erros não classificados

- Rodar `ojs-scrape` manualmente, classificar caso a caso

---

## Ordem de execução

1. ~~**Etapa 1** (SSL)~~ — ✅ +54.948 registros
2. ~~**Etapa 2a** (isolados)~~ — ✅ +8.589 registros
3. ~~**Etapa 2b** (portais por set)~~ — ✅ +453.884 registros
4. **Etapa 3** (P2 retry sets) — próximo
5. **Etapa 5** (investigar unclassified)
6. **Etapa 4** (USP) — por último