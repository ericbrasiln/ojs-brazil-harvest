# Relatório de Erros — OJS Brazil Harvest

**Data:** 2026-06-03  
**Após:** Passada 1 (coleta integral) + Passada 2 (coleta por set)

---

## Visão geral

| Métrica | Passada 1 | Passada 2 | Total |
|---------|-----------|-----------|-------|
| Targets tentados | 221 URLs | 2.361 sets (59 portais) | — |
| ✅ Sucesso | 70 (32%) | 1.828 (77%) | — |
| ⏱ Timeout | 63 (28%) | 307 (13%) | 370 |
| ❌ Erro | 88 (40%) | 226 (10%) | 314 |
| **Registros coletados** | **48.298** | **599.684** | **647.982** |

---

## 1. Erros da Passada 1 — Periódicos isolados (68 URLs)

| Categoria | Qtd | Recuperável? | Estratégia |
|-----------|-----|-------------|------------|
| HTTP 102 Processing | 22 | Parcialmente | Retry com timeout 600s; coletar na madrugada |
| SSL (certificado inválido) | 13 | Sim | Bypass SSL: `PYTHONHTTPSVERIFY=0` ou patch no ojs-scrape |
| ConnectTimeout | 13 | Parcialmente | Servidor pode estar fora; retry depois |
| XML/Parse error | 6 | Parcialmente | ojs-scrape já faz limpeza; alguns casos inescapáveis |
| ConnectionError/DNS | 6 | Não | Domínio inexistente/decomissionado |
| HTTP error (genérico) | 2 | Parcialmente | Depende do código HTTP |
| Unclassified (traceback) | 6 | ? | Precisa inspeção manual |

## 2. Erros da Passada 1 — Portais (20 URLs)

| Categoria | Qtd | Recuperável? | Estratégia |
|-----------|-----|-------------|------------|
| HTTP 102 Processing | 12 | Sim | Coletar por set (Passada 2 já tratou a maioria) |
| SSL | 4 | Sim | Bypass SSL |
| ConnectionError/DNS | 2 | Não | Domínio inexistente |
| ConnectTimeout | 1 | Parcialmente | Retry posterior |
| XML/Parse | 1 | Parcialmente | Limpeza de XML |

## 3. Timeouts da Passada 1 — Periódicos isolados (29 URLs)

Todos atingiram o limite de 240s. São periódicos com instalação própria que, ainda assim, demoram demais para responder (repositórios grandes ou servidores lentos).

**Estratégia:** Retry com timeout 600s. Estimativa de recuperação: ~15-20 destes.

---

## 4. Erros da Passada 2 — Sets com erro (226 sets em 20 portais)

Os erros na Passada 2 são mais difíceis de categorizar porque o `ojs-scrape` trunca o stderr em 500 chars e o `harvest_batch.py` trunca em 300 chars, perdendo o tipo de exceção. A análise dos padrões indica:

- **Majoria (179/226):** Trata-se de erros dentro de `ojs-scrape` durante `list_records()` — provavelmente HTTP errors (raise_for_status) ou erros de parse do XML. O tempo de resposta (>5s em 223/226 casos) indica que a conexão foi estabelecida, mas a resposta falhou.
- **Distribuição:** Erros espalhados ao longo do processamento (posição média no meio), sem padrão claro de rate limiting. Sugere problemas individuais por set, não bloqueio sistemático.

**Top portais com erros por set:**

| Portal | Total sets | OK | Erro | Timeout |
|--------|-----------|-----|------|---------|
| Periódicos da UFES | 100 | 70 | 24 | 6 |
| Portal de Periódicos da UFPB | 104 | 80 | 24 | 0 |
| OJS - UFSC | 35 | 22 | 13 | 0 |
| Portal de Conteúdo da SBC | 188 | 177 | 11 | 0 |
| SEER UFRGS | 99 | 79 | 11 | 9 |

**Estratégia:** Retry dos 226 sets com erro, com timeout maior (300s) e delay maior (2s). Estimativa de recuperação: ~100-150 sets.

## 5. Timeouts da Passada 2 — Sets com timeout (307 sets em 30 portais)

| Portal | Sets com timeout | Total sets do portal |
|--------|-----------------|---------------------|
| Portal de Revistas da USP | **194** | 194 (100%) |
| Portal de Periódicos UFU - PPUFU | 26 | 47 |
| SEER UFRGS | 9 | 99 |
| Biblioteca Digital de Periódicos UFPR | 8 | 79 |
| Portal de Revistas Científicas da UFMT | 8 | 23 |

**Destaque:** O portal da USP sozinho responde por **194 dos 307 timeouts** (63%). Todos os 194 sets falharam — provavelmente bloqueio no nível do servidor (rate limiting agressivo ou bloqueio de IP).

**Estratégia:**
- **USP:** Tentar com delay de 5-10s entre sets e/ou horário de madrugada
- **Outros:** Retry com timeout 300s e delay 2s
- Estimativa de recuperação: ~50-100 sets (excluindo USP)

## 6. Portais com 100% de falha (7 portais)

| Portal | Sets | Erro | Timeout | Diagnóstico |
|--------|------|------|---------|-------------|
| Portal de Revistas da USP | 194 | 0 | 194 | Rate limiting / bloqueio de IP |
| Portal de Periódicos UFPE | 8 | 1 | 7 | Servidor muito lento |
| Editora Unoesc | 5 | 4 | 1 | Erros HTTP por set |
| ARCHIVES OF HEALTH INVESTIGATION | 1 | 0 | 1 | Timeout |
| (sem nome) | 1 | 0 | 1 | Timeout |
| Portal de Periódicos Eletrônicos da UFOP | 1 | 1 | 0 | Erro |
| Portal de Periódicos (encoding) | 1 | 0 | 1 | Timeout |

**Estratégia:** USP merece abordagem dedicada. Os demais são casos pontuais.

---

## 7. Resumo de recuperabilidade

| Categoria | Qtd | Recuperável | Estratégia |
|-----------|-----|-------------|------------|
| P1 isolados: SSL | 13 | ✅ Sim | Bypass SSL |
| P1 isolados: HTTP 102 | 22 | ⚠️ Parcial | Timeout 600s |
| P1 isolados: ConnectTimeout | 13 | ⚠️ Parcial | Retry depois |
| P1 isolados: timeout geral | 29 | ⚠️ Parcial | Timeout 600s |
| P1 portais: SSL | 4 | ✅ Sim | Bypass SSL |
| P2 sets: erro | 226 | ⚠️ Parcial | Retry timeout 300s, delay 2s |
| P2 sets: timeout | 307 | ⚠️ Parcial | Retry timeout 300s |
| P2 sets: USP timeout | 194 | ⚠️ Difícil | Delay 5-10s, madrugada |
| DNS/ConnectionError | 14 | ❌ Não | Domínios inexistentes |
| XML/Parse | 7 | ⚠️ Parcial | Melhorar tratamento no script |

**Estimativa de ganho com estratégias de recuperação:**
- SSL bypass: +~5.000-10.000 registros
- Retry P1 timeout 600s: +~5.000-15.000 registros
- Retry P2 (erro + timeout, exceto USP): +~20.000-50.000 registros
- USP dedicado: +~50.000-100.000 registros (potencial alto, depende de resolver rate limiting)
- **Total estimado:** +80.000-175.000 registros

---

## 8. Diagnóstico estratégico para o universo completo

Com base na amostra, a estratégia ótima para escalar é:

1. **Coletar por set PRIMEIRO** para portais (pula Passada 1 para portais)
2. **Coletar sem set** para periódicos isolados (Passada 1)
3. **Retry com SSL bypass e timeout maior** como segunda rodada
4. **USP e portais agressivos** requerem abordagem dedicada (proxy, delay alto, madrugada)

Isso elimina o problema da Passada 1 desperdiçar 240s em cada portal que vai falhar de qualquer forma.