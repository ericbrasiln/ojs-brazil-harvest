# Plano de Ação — Retry de Erros da Amostra

**Branch:** `fix/retry-errors`  
**Objetivo:** Recuperar o máximo de registros dos targets que falharam na amostra, testando as estratégias antes de escalar para o universo completo.

---

## Visão geral dos 684 problemas

| Categoria | Qtd | Prioridade | Ganho estimado |
|-----------|-----|------------|-----------------|
| P1 isolados: SSL | 29 | ✅ Resolvido | +54.948 registros |
| P1 isolados: timeout/HTTP 102 | 36 | ✅ Resolvido | +8.589 (1 OK) |
| P2 sets: erro (226) | 226 | Média | +20K-40K |
| P2 sets: timeout não-USP (113) | 113 | Média | +10K-30K |
| P2 sets: USP timeout (194) | 194 | Baixa | +50K-100K (difícil) |
| P1 portais com erro | 63 | Média | tentar por set |
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

## Etapa 2b — Retry de Portais por Set (pendente)

**O que fazer:**
- Extrair os 63 portais com erro da P1/P2
- Rodar `harvest_by_set.py` com `--resume` apenas nesses portais
- Timeout 300s por set, delay 2s

**Verificação:** comparar com sets já coletados na P2 (não duplicar)

---

## Etapa 3 — Retry P2 sets com erro e timeout (226 + 113 não-USP)

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

1. ~~**Etapa 1** (SSL)~~ — ✅ concluída (+54.948 registros)
2. ~~**Etapa 2a** (isolados)~~ — ✅ concluída (+8.589 registros)
3. **Etapa 2b** (portais por set) — próximo
4. **Etapa 3** (P2 retry sets)
5. **Etapa 5** (investigar unclassified)
6. **Etapa 4** (USP) — por último